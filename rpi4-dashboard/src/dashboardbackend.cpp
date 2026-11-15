#include "dashboardbackend.h"

#include <QCoreApplication>
#include <QDBusConnection>
#include <QDBusInterface>
#include <QDir>
#include <QFile>
#include <QHash>
#include <QHostAddress>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonValue>
#include <QStandardPaths>
#include <QUrl>
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
QString DashboardBackend::distanceUnit() const { return m_distanceUnit; }
QString DashboardBackend::distanceMean() const { return m_distanceMean; }
QString DashboardBackend::distanceSpread() const { return m_distanceSpread; }
QString DashboardBackend::safetyState() const { return m_safetyState; }
QStringList DashboardBackend::safetyReasons() const { return m_safetyReasons; }
bool DashboardBackend::safetyLatched() const { return m_safetyLatched; }
bool DashboardBackend::safetyArmed() const { return m_safetyArmed; }
QString DashboardBackend::releaseFeedback() const { return m_releaseFeedback; }
QVariantList DashboardBackend::recentRecords() const { return m_recentRecords; }
QString DashboardBackend::recordFeedback() const { return m_recordFeedback; }
QString DashboardBackend::missionMode() const { return m_missionMode; }
QString DashboardBackend::missionState() const { return m_missionState; }
QString DashboardBackend::planId() const { return m_planId; }
int DashboardBackend::currentWaypoint() const { return m_currentWaypoint; }
int DashboardBackend::totalWaypoints() const { return m_totalWaypoints; }
double DashboardBackend::coverageRatio() const { return m_coverageRatio; }
bool DashboardBackend::planReady() const { return m_planReady; }
QString DashboardBackend::planOrientation() const { return m_planOrientation; }
double DashboardBackend::planEstimatedLength() const { return m_planEstimatedLength; }
int DashboardBackend::planTurnCount() const { return m_planTurnCount; }
QVariantList DashboardBackend::planWaypoints() const { return m_planWaypoints; }
QVariantList DashboardBackend::planCandidates() const { return m_planCandidates; }
bool DashboardBackend::poseValid() const { return m_poseValid; }
double DashboardBackend::poseX() const { return m_poseX; }
double DashboardBackend::poseY() const { return m_poseY; }
double DashboardBackend::poseTheta() const { return m_poseTheta; }
double DashboardBackend::planWidth() const { return m_planWidth; }
double DashboardBackend::planHeight() const { return m_planHeight; }
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
    m_releasePending = true;
    m_releaseFeedback = QStringLiteral("해제 요청을 전송했습니다. 안전 판정을 기다립니다.");
    emit safetyChanged();
    sendToRobot(QJsonObject {{QStringLiteral("type"), QStringLiteral("stop_release")}});
}

void DashboardBackend::requestRoutePlan(double width, double height, double scanWidth,
                                        double overlapRatio, double safetyMargin,
                                        const QString &startCorner)
{
    sendToRobot(QJsonObject {
        {QStringLiteral("type"), QStringLiteral("route_plan_request")},
        {QStringLiteral("area"), QJsonObject {
            {QStringLiteral("surface"), QStringLiteral("RECTANGLE")},
            {QStringLiteral("width_m"), width},
            {QStringLiteral("height_m"), height},
        }},
        {QStringLiteral("scan_width_m"), scanWidth},
        {QStringLiteral("overlap_ratio"), overlapRatio},
        {QStringLiteral("safety_margin_m"), safetyMargin},
        {QStringLiteral("start_corner"), startCorner},
    });
}

void DashboardBackend::sendAutonomyCommand(const QString &type)
{
    static const QStringList allowed {QStringLiteral("route_start"), QStringLiteral("route_pause"),
                                      QStringLiteral("route_resume"), QStringLiteral("route_cancel")};
    if (allowed.contains(type))
        sendToRobot(QJsonObject {{QStringLiteral("type"), type}});
}

void DashboardBackend::setOnScreenKeyboardVisible(bool visible)
{
    // squeekboard(라파 OS 가상 키보드)의 focus-in/out 자동 표시가 이 환경에서 불안정해서,
    // TextField 포커스 변화 때마다 D-Bus로 명시적으로 보이기/숨기기를 직접 지정한다.
    // (SetVisible은 "자동 모드로 복귀"가 없는 수동 오버라이드라, 항상 대칭으로 호출해야 한다.)
    QDBusInterface osk(QStringLiteral("sm.puri.OSK0"), QStringLiteral("/sm/puri/OSK0"),
                        QStringLiteral("sm.puri.OSK0"), QDBusConnection::sessionBus());
    if (osk.isValid())
        osk.call(QStringLiteral("SetVisible"), visible);
}

void DashboardBackend::quitApplication()
{
    QCoreApplication::quit();
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
    if (m_orinSocket == socket) {
        m_orinSocket = nullptr;
        m_lastOrinMessage = {};
        if (!m_detections.isEmpty()) {
            m_detections.clear();
            emit detectionsChanged();
        }
    }
    emit connectionChanged();
    socket->deleteLater();
}

void DashboardBackend::refreshConnectionState()
{
    const QDateTime now = QDateTime::currentDateTimeUtc();
    if (m_lastOrinMessage.isValid()
        && m_lastOrinMessage.msecsTo(now) > kOnlineTimeoutMs
        && !m_detections.isEmpty()) {
        m_detections.clear();
        emit detectionsChanged();
    }
    if (m_lastRobotMessage.isValid()
        && m_lastRobotMessage.msecsTo(now) > kOnlineTimeoutMs
        && (m_safetyState != QLatin1String("OFFLINE") || !m_safetyLatched)) {
        m_safetyState = QStringLiteral("OFFLINE");
        m_safetyReasons = {QStringLiteral("로봇 상태 수신 지연")};
        m_safetyLatched = true;
        m_safetyArmed = false;
        emit safetyChanged();
    }
    emit connectionChanged();
}

void DashboardBackend::handleStatus(QWebSocket *socket, const QJsonObject &message)
{
    m_robotSocket = socket;
    m_lastRobotMessage = QDateTime::currentDateTimeUtc();
    m_lastStatus = message;
    m_battery = numberText(message.value(QStringLiteral("battery")), QStringLiteral(" V"));

    const QJsonObject imu = message.value(QStringLiteral("imu")).toObject();
    m_roll = numberText(imu.value(QStringLiteral("roll")), QStringLiteral("°"));
    m_pitch = numberText(imu.value(QStringLiteral("pitch")), QStringLiteral("°"));
    m_yaw = numberText(imu.value(QStringLiteral("yaw")), QStringLiteral("°"));

    const QJsonObject distanceMeta = message.value(QStringLiteral("distance_meta")).toObject();
    const bool calibrated = distanceMeta.value(QStringLiteral("calibrated")).toBool(false);
    const QString suppliedUnit = distanceMeta.value(QStringLiteral("unit")).toString().toUpper();
    m_distanceUnit = calibrated ? (suppliedUnit.isEmpty() ? QStringLiteral("MM") : suppliedUnit)
                                : (suppliedUnit == QLatin1String("ADC") ? QStringLiteral("ADC") : QStringLiteral("REL"));
    const QString suffix = QStringLiteral(" ") + m_distanceUnit;
    const QJsonArray distances = message.value(QStringLiteral("distance")).toArray();
    m_distances = {"--", "--", "--"};
    for (qsizetype i = 0; i < distances.size() && i < m_distances.size(); ++i)
        m_distances[i] = numberText(distances.at(i), suffix, true);
    m_distanceMean = numberText(distanceMeta.value(QStringLiteral("mean")), suffix, true);
    m_distanceSpread = numberText(distanceMeta.value(QStringLiteral("spread")), suffix);

    const QJsonObject mission = message.value(QStringLiteral("mission")).toObject();
    m_missionMode = mission.value(QStringLiteral("mode")).toString(QStringLiteral("MANUAL"));
    m_missionState = mission.value(QStringLiteral("state")).toString(QStringLiteral("IDLE"));
    m_planId = mission.value(QStringLiteral("plan_id")).toString();
    m_currentWaypoint = mission.value(QStringLiteral("current_waypoint")).toInt(0);
    m_totalWaypoints = mission.value(QStringLiteral("total_waypoints")).toInt(0);
    m_coverageRatio = qBound(0.0, mission.value(QStringLiteral("coverage_ratio")).toDouble(0.0), 1.0);
    const QJsonObject plan = message.value(QStringLiteral("plan")).toObject();
    m_planReady = !plan.isEmpty() && !plan.value(QStringLiteral("waypoints")).toArray().isEmpty();
    m_planOrientation = plan.value(QStringLiteral("orientation")).toString();
    m_planEstimatedLength = plan.value(QStringLiteral("estimated_length_m")).toDouble(0.0);
    m_planTurnCount = plan.value(QStringLiteral("turn_count")).toInt(0);
    m_planWidth = plan.value(QStringLiteral("width_m")).toDouble(0.0);
    m_planHeight = plan.value(QStringLiteral("height_m")).toDouble(0.0);
    m_planWaypoints.clear();
    for (const QJsonValue &value : plan.value(QStringLiteral("waypoints")).toArray())
        m_planWaypoints.append(value.toObject().toVariantMap());
    m_planCandidates.clear();
    for (const QJsonValue &value : plan.value(QStringLiteral("candidates")).toArray())
        m_planCandidates.append(value.toObject().toVariantMap());

    // Prefer mission.plan_pose: it is the live pose already expressed in the plan's own
    // coordinates, which is the frame the execution diagram is drawn in. The raw /pose
    // fallback is relative to odometry's power-on origin and only lines up with the drawing
    // before a route is anchored.
    const QJsonValue planPoseValue = mission.value(QStringLiteral("plan_pose"));
    const QJsonValue poseValue = message.value(QStringLiteral("pose"));
    const QJsonObject pose = planPoseValue.isObject() ? planPoseValue.toObject()
                                                      : poseValue.toObject();
    m_poseValid = planPoseValue.isObject()
        || (poseValue.isObject() && pose.value(QStringLiteral("calibrated")).toBool(false));
    m_poseX = pose.value(QStringLiteral("x")).toDouble(0.0);
    m_poseY = pose.value(QStringLiteral("y")).toDouble(0.0);
    m_poseTheta = pose.value(QStringLiteral("theta")).toDouble(0.0);
    m_poseSource = planPoseValue.isObject()
        ? QStringLiteral("PLAN_FRAME")
        : (m_poseValid ? QStringLiteral("ENCODER_ODOMETRY")
                       : QStringLiteral("UNAVAILABLE"));
    // Safety transitions may request an immediate inspection record.  Update it only after
    // this same status packet's mission and pose fields have been committed, so the event
    // cannot be tagged with the previous waypoint.
    updateSafety(message);

    emit telemetryChanged();
    emit missionChanged();
    emit connectionChanged();
}

void DashboardBackend::updateSafety(const QJsonObject &message)
{
    const QJsonObject safety = message.value(QStringLiteral("safety")).toObject();
    const QString previousState = m_safetyState;
    const bool hadSafetyState = m_receivedSafetyState;
    if (safety.isEmpty()) {
        m_safetyState = QStringLiteral("OFFLINE");
        m_safetyReasons = {QStringLiteral("sensor_waiting")};
        m_safetyLatched = true;
        m_safetyArmed = false;
    } else {
        m_receivedSafetyState = true;
        m_safetyState = safety.value(QStringLiteral("state")).toString(QStringLiteral("OFFLINE")).toUpper();
        m_safetyLatched = safety.value(QStringLiteral("latched")).toBool(false);
        m_safetyArmed = safety.value(QStringLiteral("armed")).toBool(false);
        m_safetyReasons.clear();
        const QJsonArray reasons = safety.value(QStringLiteral("reasons")).toArray();
        for (const QJsonValue &value : reasons)
            m_safetyReasons.append(reasonText(value.toString()));
    }
    if (m_releasePending && m_safetyState == QLatin1String("NORMAL") && !m_safetyLatched) {
        m_releaseFeedback = QStringLiteral("안전 조건이 확인되어 정지가 해제됐습니다.");
        m_releasePending = false;
    } else if (m_releasePending
               && safety.value(QStringLiteral("reasons")).toArray().contains(
                   QJsonValue(QStringLiteral("release_rejected")))) {
        m_releaseFeedback = QStringLiteral("해제 거부: ") + m_safetyReasons.join(QStringLiteral(" · "));
        m_releasePending = false;
    }
    emit safetyChanged();
    if (hadSafetyState && previousState != QLatin1String("STOPPED")
        && m_safetyState == QLatin1String("STOPPED"))
        emit safetyRecordRequested(QStringLiteral("SAFETY_STOP"));
}

void DashboardBackend::handleDetections(QWebSocket *socket, const QJsonObject &message)
{
    m_orinSocket = socket;
    m_lastOrinMessage = QDateTime::currentDateTimeUtc();
    m_detections.clear();

    const QJsonArray detections = message.value(QStringLiteral("detections")).toArray();
    for (const QJsonValue &value : detections) {
        if (!value.isObject())
            continue;
        const QJsonObject detection = value.toObject();
        const double rawX = detection.value(QStringLiteral("x")).toDouble(qQNaN());
        const double rawY = detection.value(QStringLiteral("y")).toDouble(qQNaN());
        const double rawWidth = detection.value(QStringLiteral("width")).toDouble(qQNaN());
        const double rawHeight = detection.value(QStringLiteral("height")).toDouble(qQNaN());
        const double rawConfidence = detection.value(QStringLiteral("confidence")).toDouble(qQNaN());
        if (!qIsFinite(rawX) || !qIsFinite(rawY) || !qIsFinite(rawWidth)
            || !qIsFinite(rawHeight) || !qIsFinite(rawConfidence)
            || rawWidth <= 0.0 || rawHeight <= 0.0)
            continue;
        const double x = qBound(0.0, rawX, 1.0);
        const double y = qBound(0.0, rawY, 1.0);
        const double width = qBound(0.0, rawWidth, 1.0 - x);
        const double height = qBound(0.0, rawHeight, 1.0 - y);
        if (qFuzzyIsNull(width) || qFuzzyIsNull(height))
            continue;
        QVariantMap item;
        item.insert(QStringLiteral("x"), x);
        item.insert(QStringLiteral("y"), y);
        item.insert(QStringLiteral("width"), width);
        item.insert(QStringLiteral("height"), height);
        item.insert(QStringLiteral("label"),
                    detection.value(QStringLiteral("label"))
                        .toString(QStringLiteral("defect")).left(64));
        item.insert(QStringLiteral("confidence"), qBound(0.0, rawConfidence, 1.0));
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
    m_distanceUnit = QStringLiteral("REL");
    m_distances = {
        QString::number(78 + qRound(qSin(phase) * 4)) + QStringLiteral(" REL"),
        QString::number(80 + qRound(qCos(phase) * 3)) + QStringLiteral(" REL"),
        QString::number(79 + qRound(qSin(phase * 0.7) * 5)) + QStringLiteral(" REL"),
    };
    m_distanceMean = QStringLiteral("79 REL");
    m_distanceSpread = QStringLiteral("5 REL");
    m_safetyState = QStringLiteral("NORMAL");
    m_safetyReasons.clear();
    m_safetyLatched = false;
    m_safetyArmed = false;

    // Demo mode validates the console without presenting a fictional defect alert.
    if (!m_detections.isEmpty())
        m_detections.clear();
    emit telemetryChanged();
    emit safetyChanged();
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

QString DashboardBackend::numberText(const QJsonValue &value, const QString &suffix, bool zeroUnavailable)
{
    if (!value.isDouble() || (zeroUnavailable && qFuzzyIsNull(value.toDouble())))
        return QStringLiteral("--");
    return QString::number(value.toDouble(), 'f', 1) + suffix;
}

QString DashboardBackend::captureStagingPath()
{
    const QString stagingDir = QStandardPaths::writableLocation(QStandardPaths::AppDataLocation)
        + QStringLiteral("/records/.staging");
    QDir().mkpath(stagingDir);
    return stagingDir + QStringLiteral("/latest-frame.png");
}

bool DashboardBackend::saveInspectionRecord(const QString &stagingImagePath,
                                            const QString &errorMessage,
                                            const QString &trigger)
{
    const QDateTime now = QDateTime::currentDateTime();
    const QString date = now.toString(QStringLiteral("yyyy-MM-dd"));
    const QString id = now.toString(QStringLiteral("yyyyMMdd-HHmmss-zzz"));
    const QString base = QStandardPaths::writableLocation(QStandardPaths::AppDataLocation)
        + QStringLiteral("/records/") + date;
    QDir().mkpath(base);
    const QString imagePath = base + QStringLiteral("/") + id + QStringLiteral(".png");
    bool imageSaved = false;
    QString imageError = errorMessage;
    if (imageError.isEmpty() && !stagingImagePath.isEmpty()) {
        QFile::remove(imagePath);
        imageSaved = QFile::copy(stagingImagePath, imagePath);
        if (!imageSaved)
            imageError = QStringLiteral("프레임 파일을 기록 폴더로 복사하지 못했습니다.");
    } else if (imageError.isEmpty()) {
        imageError = QStringLiteral("수신 중인 실제 영상 프레임이 없습니다.");
    }
    QJsonArray detectionSnapshot;
    for (const QVariant &value : m_detections)
        detectionSnapshot.append(QJsonObject::fromVariantMap(value.toMap()));
    const QJsonValue planId = m_planId.isEmpty() ? QJsonValue(QJsonValue::Null)
                                                 : QJsonValue(m_planId);
    const QJsonObject pose = m_poseValid
        ? QJsonObject {{QStringLiteral("x"), m_poseX},
                       {QStringLiteral("y"), m_poseY},
                       {QStringLiteral("theta"), m_poseTheta}}
        : QJsonObject {};
    const QString recordTrigger = trigger.trimmed().isEmpty()
        ? QStringLiteral("OPERATOR") : trigger.trimmed().left(64);
    QJsonObject metadata {
        {QStringLiteral("record_id"), id},
        {QStringLiteral("time"), now.toString(Qt::ISODateWithMs)},
        {QStringLiteral("trigger"), recordTrigger},
        {QStringLiteral("image"), imageSaved ? QJsonValue(imagePath) : QJsonValue(QJsonValue::Null)},
        {QStringLiteral("plan_id"), planId},
        {QStringLiteral("waypoint"), m_planId.isEmpty() ? -1 : m_currentWaypoint},
        {QStringLiteral("pose_source"), m_poseSource},
        {QStringLiteral("pose"), pose},
        {QStringLiteral("note"), QString()},
        {QStringLiteral("imu"), m_lastStatus.value(QStringLiteral("imu")).toObject()},
        {QStringLiteral("distance"), m_lastStatus.value(QStringLiteral("distance"))},
        {QStringLiteral("distance_meta"), m_lastStatus.value(QStringLiteral("distance_meta"))},
        {QStringLiteral("battery"), m_lastStatus.value(QStringLiteral("battery"))},
        {QStringLiteral("battery_meta"), m_lastStatus.value(QStringLiteral("battery_meta"))},
        {QStringLiteral("stm32"), m_lastStatus.value(QStringLiteral("stm32"))},
        {QStringLiteral("mission"), m_lastStatus.value(QStringLiteral("mission"))},
        {QStringLiteral("detections"), detectionSnapshot},
        {QStringLiteral("safety_state"), m_safetyState},
        {QStringLiteral("reasons"), QJsonArray::fromStringList(m_safetyReasons)},
    };
    if (!imageSaved)
        metadata.insert(QStringLiteral("image_error"), imageError);
    QFile log(base + QStringLiteral("/records.jsonl"));
    if (!log.open(QIODevice::WriteOnly | QIODevice::Append | QIODevice::Text)) {
        m_recordFeedback = QStringLiteral("기록 메타데이터를 저장하지 못했습니다.");
        emit recordsChanged();
        return false;
    }
    log.write(QJsonDocument(metadata).toJson(QJsonDocument::Compact) + '\n');
    QVariantMap record {{QStringLiteral("recordId"), id}, {QStringLiteral("time"), now.toString(QStringLiteral("HH:mm:ss"))}, {QStringLiteral("image"), imageSaved ? QUrl::fromLocalFile(imagePath).toString() : QString()}, {QStringLiteral("state"), m_safetyState}, {QStringLiteral("saved"), imageSaved}};
    m_recentRecords.prepend(record);
    while (m_recentRecords.size() > 3)
        m_recentRecords.removeLast();
    m_recordFeedback = imageSaved ? QStringLiteral("점검 기록 저장 완료 · ") + id : QStringLiteral("메타데이터 저장 · 이미지 실패: ") + imageError;
    emit recordsChanged();
    return imageSaved;
}

QVariantList DashboardBackend::loadAllRecords()
{
    QVariantList all;
    const QString rootPath = QStandardPaths::writableLocation(QStandardPaths::AppDataLocation)
        + QStringLiteral("/records");
    QDir root(rootPath);
    const QStringList dateDirs = root.entryList(QDir::Dirs | QDir::NoDotAndDotDot, QDir::Name | QDir::Reversed);
    for (const QString &dateDir : dateDirs) {
        if (dateDir == QStringLiteral(".staging"))
            continue;
        QFile log(rootPath + QStringLiteral("/") + dateDir + QStringLiteral("/records.jsonl"));
        if (!log.open(QIODevice::ReadOnly | QIODevice::Text))
            continue;
        QList<QByteArray> lines = log.readAll().split('\n');
        for (auto it = lines.crbegin(); it != lines.crend(); ++it) {
            const QByteArray &line = *it;
            if (line.trimmed().isEmpty())
                continue;
            const QJsonObject entry = QJsonDocument::fromJson(line).object();
            if (entry.isEmpty())
                continue;
            const QString imagePath = entry.value(QStringLiteral("image")).toString();
            const bool saved = !imagePath.isEmpty() && QFile::exists(imagePath);
            const QJsonObject imu = entry.value(QStringLiteral("imu")).toObject();
            const QJsonArray distance = entry.value(QStringLiteral("distance")).toArray();
            const auto displayValue = [](const QJsonValue &value) {
                if (value.isString())
                    return value.toString();
                if (value.isDouble())
                    return QString::number(value.toDouble(), 'f', 2);
                return QStringLiteral("--");
            };
            QStringList distanceStrings;
            for (const auto &d : distance)
                distanceStrings << displayValue(d);
            const QJsonObject pose = entry.value(QStringLiteral("pose")).toObject();
            const QString poseText = pose.contains(QStringLiteral("x"))
                ? QStringLiteral("x=%1 y=%2 θ=%3")
                      .arg(pose.value(QStringLiteral("x")).toDouble(), 0, 'f', 2)
                      .arg(pose.value(QStringLiteral("y")).toDouble(), 0, 'f', 2)
                      .arg(pose.value(QStringLiteral("theta")).toDouble(), 0, 'f', 2)
                : QString();
            QStringList reasonStrings;
            for (const auto &reason : entry.value(QStringLiteral("reasons")).toArray())
                reasonStrings << reasonText(reason.toString());
            const int waypoint = entry.value(QStringLiteral("waypoint")).toInt(-1);
            all.append(QVariantMap {
                {QStringLiteral("recordId"), entry.value(QStringLiteral("record_id")).toString()},
                {QStringLiteral("date"), dateDir},
                {QStringLiteral("time"), entry.value(QStringLiteral("time")).toString()},
                {QStringLiteral("image"), saved ? QUrl::fromLocalFile(imagePath).toString() : QString()},
                {QStringLiteral("saved"), saved},
                {QStringLiteral("imageError"), entry.value(QStringLiteral("image_error")).toString()},
                {QStringLiteral("safetyState"), entry.value(QStringLiteral("safety_state")).toString()},
                {QStringLiteral("roll"), displayValue(imu.value(QStringLiteral("roll")))},
                {QStringLiteral("pitch"), displayValue(imu.value(QStringLiteral("pitch")))},
                {QStringLiteral("yaw"), displayValue(imu.value(QStringLiteral("yaw")))},
                {QStringLiteral("distance"), distanceStrings.join(QStringLiteral(" / "))},
                {QStringLiteral("trigger"), entry.value(QStringLiteral("trigger")).toString()},
                {QStringLiteral("planId"), entry.value(QStringLiteral("plan_id")).toString()},
                {QStringLiteral("waypoint"), waypoint},
                {QStringLiteral("poseSource"), entry.value(QStringLiteral("pose_source")).toString()},
                {QStringLiteral("pose"), poseText},
                {QStringLiteral("note"), entry.value(QStringLiteral("note")).toString()},
                {QStringLiteral("reasons"), reasonStrings.join(QStringLiteral(" · "))},
            });
        }
    }
    return all;
}

bool DashboardBackend::deleteRecord(const QString &date, const QString &recordId)
{
    const QString base = QStandardPaths::writableLocation(QStandardPaths::AppDataLocation)
        + QStringLiteral("/records/") + date;
    QFile log(base + QStringLiteral("/records.jsonl"));
    if (!log.open(QIODevice::ReadOnly | QIODevice::Text))
        return false;
    const QList<QByteArray> lines = log.readAll().split('\n');
    log.close();

    QByteArray kept;
    QString imagePath;
    bool found = false;
    for (const QByteArray &line : lines) {
        if (line.trimmed().isEmpty())
            continue;
        const QJsonObject entry = QJsonDocument::fromJson(line).object();
        if (!found && entry.value(QStringLiteral("record_id")).toString() == recordId) {
            found = true;
            imagePath = entry.value(QStringLiteral("image")).toString();
            continue;
        }
        kept += line + '\n';
    }
    if (!found)
        return false;
    if (!log.open(QIODevice::WriteOnly | QIODevice::Truncate | QIODevice::Text))
        return false;
    log.write(kept);
    log.close();
    if (!imagePath.isEmpty())
        QFile::remove(imagePath);
    m_recordFeedback = QStringLiteral("기록 삭제 완료 · ") + recordId;
    emit recordsChanged();
    return true;
}

QString DashboardBackend::reasonText(const QString &reason)
{
    static const QHash<QString, QString> labels {
        {QStringLiteral("sensor_waiting"), QStringLiteral("센서 연결 대기")},
        {QStringLiteral("awaiting_sensors"), QStringLiteral("센서 연결 대기")},
        {QStringLiteral("stm32_offline"), QStringLiteral("STM32 연결 끊김")},
        {QStringLiteral("stm32_flags_stale"), QStringLiteral("STM32 안전상태 수신 지연")},
        {QStringLiteral("stm32_timeout_seen"), QStringLiteral("STM32 통신 타임아웃 이력")},
        {QStringLiteral("stm32_stop_latched"), QStringLiteral("STM32 정지 래치 유지")},
        {QStringLiteral("battery_stale"), QStringLiteral("배터리 상태 수신 지연")},
        {QStringLiteral("battery_invalid"), QStringLiteral("배터리 측정 회로 확인 필요")},
        {QStringLiteral("battery_warning"), QStringLiteral("배터리 저전압 경고")},
        {QStringLiteral("battery_stop_latched"), QStringLiteral("배터리 저전압 정지")},
        {QStringLiteral("distance_stale"), QStringLiteral("거리센서 수신 지연")},
        {QStringLiteral("distance_invalid"), QStringLiteral("거리센서 범위 이탈")},
        {QStringLiteral("distance_not_required"), QStringLiteral("거리센서 미장착(벤치 시험 모드)")},
        {QStringLiteral("imu_stale"), QStringLiteral("IMU 수신 지연")},
        {QStringLiteral("spread_high"), QStringLiteral("3점 거리 편차")},
        {QStringLiteral("gyro_spike"), QStringLiteral("급격한 회전")},
        {QStringLiteral("accel_spike"), QStringLiteral("급격한 가속 충격")},
        {QStringLiteral("startup_grace"), QStringLiteral("기동 안정화 대기")},
        {QStringLiteral("release_waiting_stable"), QStringLiteral("해제 안정시간 확인 중")},
        {QStringLiteral("release_waiting_stm32"), QStringLiteral("STM32 정지 해제 확인 중")},
        {QStringLiteral("release_rejected"), QStringLiteral("정지 해제 조건 미충족")},
        {QStringLiteral("manual_stop"), QStringLiteral("수동 비상 정지")},
    };
    return labels.value(reason, reason.isEmpty() ? QStringLiteral("안전 상태 확인 중") : reason);
}
