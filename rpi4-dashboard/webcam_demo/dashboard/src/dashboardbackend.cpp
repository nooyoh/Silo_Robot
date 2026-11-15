#include "dashboardbackend.h"

#include <QHostAddress>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QWebSocket>
#include <QWebSocketServer>
#include <QtMath>

namespace {
constexpr int kWebSocketPort = 8765;
constexpr int kOnlineTimeoutMs = 3000;
}

DashboardBackend::DashboardBackend(QObject *parent)
    : QObject(parent)
    , m_settings(QStringLiteral("SiloRobot"), QStringLiteral("Dashboard"))
    , m_server(new QWebSocketServer(QStringLiteral("SiloRobot Dashboard"), QWebSocketServer::NonSecureMode, this))
{
    m_rtspUrl = m_settings.value(QStringLiteral("connection/rtspUrl")).toString();
    m_advertisedHost = m_settings.value(QStringLiteral("connection/advertisedHost"), QStringLiteral("100.74.141.112")).toString();
    m_websocketPort = m_settings.value(QStringLiteral("connection/websocketPort"), kWebSocketPort).toInt();
    if (m_websocketPort < 1 || m_websocketPort > 65535)
        m_websocketPort = kWebSocketPort;

    connect(m_server, &QWebSocketServer::newConnection, this, &DashboardBackend::onNewWebSocketConnection);
    startWebSocketServer(m_websocketPort);

    m_connectionTimer.setInterval(500);
    connect(&m_connectionTimer, &QTimer::timeout, this, &DashboardBackend::refreshConnectionState);
    m_connectionTimer.start();

    m_demoTimer.setInterval(100);
    connect(&m_demoTimer, &QTimer::timeout, this, &DashboardBackend::setDemoTelemetry);
}

QString DashboardBackend::rtspUrl() const { return m_rtspUrl; }

void DashboardBackend::setRtspUrl(const QString &url)
{
    if (m_rtspUrl == url)
        return;
    m_rtspUrl = url;
    m_settings.setValue(QStringLiteral("connection/rtspUrl"), m_rtspUrl);
    emit rtspUrlChanged();
}

QString DashboardBackend::liveImagePath() const { return m_liveImagePath; }

void DashboardBackend::setLiveImagePath(const QString &path)
{
    // 로컬 데모 전용 — QSettings 에 저장하지 않음(실제 배포 설정과 안 섞이게).
    if (m_liveImagePath == path)
        return;
    m_liveImagePath = path;
    emit liveImagePathChanged();
}

QString DashboardBackend::advertisedHost() const { return m_advertisedHost; }

QString DashboardBackend::dashboardEndpoint() const
{
    return QStringLiteral("ws://%1:%2").arg(m_advertisedHost, QString::number(m_websocketPort));
}

QString DashboardBackend::battery() const { return m_battery; }
QString DashboardBackend::roll() const { return m_roll; }
QString DashboardBackend::pitch() const { return m_pitch; }
QString DashboardBackend::yaw() const { return m_yaw; }
QStringList DashboardBackend::distances() const { return m_distances; }
bool DashboardBackend::robotOnline() const
{
    return m_lastRobotMessage.isValid()
        && m_lastRobotMessage.msecsTo(QDateTime::currentDateTimeUtc()) <= kOnlineTimeoutMs;
}

bool DashboardBackend::orinOnline() const
{
    return m_lastOrinMessage.isValid()
        && m_lastOrinMessage.msecsTo(QDateTime::currentDateTimeUtc()) <= kOnlineTimeoutMs;
}
QString DashboardBackend::connectionSummary() const
{
    if (robotOnline() && orinOnline())
        return QStringLiteral("ROBOT + VISION ONLINE");
    if (robotOnline())
        return QStringLiteral("ROBOT ONLINE · VISION WAITING");
    if (orinOnline())
        return QStringLiteral("VISION ONLINE · ROBOT WAITING");
    return QStringLiteral("WAITING FOR ROBOT");
}
QVariantList DashboardBackend::detections() const { return m_detections; }
int DashboardBackend::websocketPort() const { return m_websocketPort; }
bool DashboardBackend::demoMode() const { return m_demoMode; }

void DashboardBackend::sendMove(int throttle, int turn)
{
    sendToRobot(QJsonObject {
        {QStringLiteral("type"), QStringLiteral("move")},
        {QStringLiteral("throttle"), clampAxis(throttle)},
        {QStringLiteral("turn"), clampAxis(turn)},
    });
}

void DashboardBackend::emergencyStop()
{
    sendToRobot(QJsonObject {{QStringLiteral("type"), QStringLiteral("stop")}});
}

void DashboardBackend::releaseEmergencyStop()
{
    sendToRobot(QJsonObject {{QStringLiteral("type"), QStringLiteral("stop_release")}});
}

void DashboardBackend::setDemoMode(bool enabled)
{
    if (m_demoMode == enabled)
        return;
    m_demoMode = enabled;
    if (enabled) {
        m_lastRobotMessage = QDateTime::currentDateTimeUtc();
        m_lastOrinMessage = m_lastRobotMessage;
        m_demoTimer.start();
        setDemoTelemetry();
    } else {
        m_demoTimer.stop();
        m_detections.clear();
        emit detectionsChanged();
    }
    emit connectionChanged();
    emit demoModeChanged();
}

bool DashboardBackend::saveConnectionSettings(const QString &advertisedHost, const QString &rtspUrl, int websocketPort)
{
    const QString trimmedHost = advertisedHost.trimmed();
    const QString trimmedRtsp = rtspUrl.trimmed();
    if (trimmedHost.isEmpty() || websocketPort < 1 || websocketPort > 65535) {
        emit websocketServerError(QStringLiteral("주소 또는 포트가 올바르지 않습니다."));
        return false;
    }

    const int previousPort = m_websocketPort;
    if (websocketPort != previousPort && !startWebSocketServer(websocketPort)) {
        startWebSocketServer(previousPort);
        return false;
    }

    m_advertisedHost = trimmedHost;
    m_websocketPort = websocketPort;
    m_settings.setValue(QStringLiteral("connection/advertisedHost"), m_advertisedHost);
    m_settings.setValue(QStringLiteral("connection/websocketPort"), m_websocketPort);
    setRtspUrl(trimmedRtsp);
    m_settings.sync();
    emit connectionSettingsChanged();
    return true;
}

void DashboardBackend::onNewWebSocketConnection()
{
    auto *socket = m_server->nextPendingConnection();
    connect(socket, &QWebSocket::textMessageReceived, this, &DashboardBackend::onSocketTextMessage);
    connect(socket, &QWebSocket::disconnected, this, &DashboardBackend::onSocketDisconnected);
}

void DashboardBackend::onSocketTextMessage(const QString &message)
{
    auto *socket = qobject_cast<QWebSocket *>(sender());
    if (!socket)
        return;

    QJsonParseError error;
    const QJsonDocument document = QJsonDocument::fromJson(message.toUtf8(), &error);
    if (error.error != QJsonParseError::NoError || !document.isObject())
        return;

    const QJsonObject object = document.object();
    const QString type = object.value(QStringLiteral("type")).toString();
    if (type == QLatin1String("status"))
        handleStatus(socket, object);
    else if (type == QLatin1String("detection"))
        handleDetections(socket, object);
    else if (type == QLatin1String("hello")) {
        const QString role = object.value(QStringLiteral("role")).toString();
        if (role == QLatin1String("nano"))
            m_robotSocket = socket;
        else if (role == QLatin1String("orin"))
            m_orinSocket = socket;
        emit connectionChanged();
    }
}

void DashboardBackend::onSocketDisconnected()
{
    auto *socket = qobject_cast<QWebSocket *>(sender());
    if (m_robotSocket == socket)
        m_robotSocket = nullptr;
    if (m_orinSocket == socket)
        m_orinSocket = nullptr;
    emit connectionChanged();
    socket->deleteLater();
}

void DashboardBackend::refreshConnectionState()
{
    emit connectionChanged();
}

void DashboardBackend::handleStatus(QWebSocket *socket, const QJsonObject &message)
{
    m_robotSocket = socket;
    m_lastRobotMessage = QDateTime::currentDateTimeUtc();
    m_battery = numberText(message.value(QStringLiteral("battery")), QStringLiteral(" V"));

    const QJsonObject imu = message.value(QStringLiteral("imu")).toObject();
    m_roll = numberText(imu.value(QStringLiteral("roll")), QStringLiteral("°"));
    m_pitch = numberText(imu.value(QStringLiteral("pitch")), QStringLiteral("°"));
    m_yaw = numberText(imu.value(QStringLiteral("yaw")), QStringLiteral("°"));

    const QJsonArray distances = message.value(QStringLiteral("distance")).toArray();
    m_distances = {"--", "--", "--"};
    for (qsizetype i = 0; i < distances.size() && i < m_distances.size(); ++i)
        m_distances[i] = numberText(distances.at(i), QStringLiteral(" mm"));

    emit telemetryChanged();
    emit connectionChanged();
}

void DashboardBackend::handleDetections(QWebSocket *socket, const QJsonObject &message)
{
    m_orinSocket = socket;
    m_lastOrinMessage = QDateTime::currentDateTimeUtc();
    m_detections.clear();

    const QJsonArray detections = message.value(QStringLiteral("detections")).toArray();
    for (const QJsonValue &value : detections) {
        const QJsonObject detection = value.toObject();
        QVariantMap item;
        item.insert(QStringLiteral("x"), detection.value(QStringLiteral("x")).toDouble());
        item.insert(QStringLiteral("y"), detection.value(QStringLiteral("y")).toDouble());
        item.insert(QStringLiteral("width"), detection.value(QStringLiteral("width")).toDouble());
        item.insert(QStringLiteral("height"), detection.value(QStringLiteral("height")).toDouble());
        item.insert(QStringLiteral("label"), detection.value(QStringLiteral("label")).toString(QStringLiteral("defect")));
        item.insert(QStringLiteral("confidence"), detection.value(QStringLiteral("confidence")).toDouble());

        // polygon: [[x,y], [x,y], ...] 정규화 좌표 (세그멘테이션 마스크 윤곽선, 선택 필드)
        QVariantList polygon;
        const QJsonArray polygonPoints = detection.value(QStringLiteral("polygon")).toArray();
        for (const QJsonValue &pointValue : polygonPoints) {
            const QJsonArray point = pointValue.toArray();
            if (point.size() != 2)
                continue;
            QVariantMap pt;
            pt.insert(QStringLiteral("x"), point.at(0).toDouble());
            pt.insert(QStringLiteral("y"), point.at(1).toDouble());
            polygon.append(pt);
        }
        item.insert(QStringLiteral("polygon"), polygon);

        m_detections.append(item);
    }
    emit detectionsChanged();
    emit connectionChanged();
}

void DashboardBackend::sendToRobot(const QJsonObject &message)
{
    if (m_robotSocket)
        m_robotSocket->sendTextMessage(QString::fromUtf8(QJsonDocument(message).toJson(QJsonDocument::Compact)));
}

void DashboardBackend::setDemoTelemetry()
{
    ++m_demoTick;
    const double phase = m_demoTick / 20.0;
    m_battery = QString::number(11.5 + qSin(phase) * 0.1, 'f', 2) + QStringLiteral(" V");
    m_roll = QString::number(qSin(phase) * 2.4, 'f', 1) + QStringLiteral("°");
    m_pitch = QString::number(qCos(phase) * 1.6, 'f', 1) + QStringLiteral("°");
    m_yaw = QString::number(qSin(phase / 2) * 14.0, 'f', 1) + QStringLiteral("°");
    m_distances = {
        QString::number(78 + qRound(qSin(phase) * 4)) + QStringLiteral(" mm"),
        QString::number(80 + qRound(qCos(phase) * 3)) + QStringLiteral(" mm"),
        QString::number(79 + qRound(qSin(phase * 0.7) * 5)) + QStringLiteral(" mm"),
    };

    // Demo mode validates the console without presenting a fictional defect alert.
    if (!m_detections.isEmpty())
        m_detections.clear();
    emit telemetryChanged();
    emit detectionsChanged();
}

bool DashboardBackend::startWebSocketServer(int port)
{
    m_server->close();
    if (!m_server->listen(QHostAddress::Any, port)) {
        emit websocketServerError(m_server->errorString());
        return false;
    }
    return true;
}

int DashboardBackend::clampAxis(int value)
{
    return qBound(-100, value, 100);
}

QString DashboardBackend::numberText(const QJsonValue &value, const QString &suffix)
{
    if (!value.isDouble())
        return QStringLiteral("--");
    return QString::number(value.toDouble(), 'f', 1) + suffix;
}
