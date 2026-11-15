#pragma once

#include <QDateTime>
#include <QObject>
#include <QPointer>
#include <QSettings>
#include <QTimer>
#include <QVariantList>

class QWebSocket;
class QWebSocketServer;

class DashboardBackend final : public QObject
{
    Q_OBJECT
    Q_PROPERTY(QString rtspUrl READ rtspUrl WRITE setRtspUrl NOTIFY rtspUrlChanged)
    // 로컬 웹캠 데모 전용(저지연 스냅샷 미리보기) — 실제 배포에서는 사용 안 함.
    Q_PROPERTY(QString liveImagePath READ liveImagePath WRITE setLiveImagePath NOTIFY liveImagePathChanged)
    Q_PROPERTY(QString advertisedHost READ advertisedHost NOTIFY connectionSettingsChanged)
    Q_PROPERTY(QString dashboardEndpoint READ dashboardEndpoint NOTIFY connectionSettingsChanged)
    Q_PROPERTY(QString battery READ battery NOTIFY telemetryChanged)
    Q_PROPERTY(QString roll READ roll NOTIFY telemetryChanged)
    Q_PROPERTY(QString pitch READ pitch NOTIFY telemetryChanged)
    Q_PROPERTY(QString yaw READ yaw NOTIFY telemetryChanged)
    Q_PROPERTY(QStringList distances READ distances NOTIFY telemetryChanged)
    Q_PROPERTY(bool robotOnline READ robotOnline NOTIFY connectionChanged)
    Q_PROPERTY(bool orinOnline READ orinOnline NOTIFY connectionChanged)
    Q_PROPERTY(QString connectionSummary READ connectionSummary NOTIFY connectionChanged)
    Q_PROPERTY(QVariantList detections READ detections NOTIFY detectionsChanged)
    Q_PROPERTY(int websocketPort READ websocketPort NOTIFY connectionSettingsChanged)
    Q_PROPERTY(bool demoMode READ demoMode NOTIFY demoModeChanged)

public:
    explicit DashboardBackend(QObject *parent = nullptr);

    QString rtspUrl() const;
    void setRtspUrl(const QString &url);
    QString liveImagePath() const;
    void setLiveImagePath(const QString &path);
    QString advertisedHost() const;
    QString dashboardEndpoint() const;
    QString battery() const;
    QString roll() const;
    QString pitch() const;
    QString yaw() const;
    QStringList distances() const;
    bool robotOnline() const;
    bool orinOnline() const;
    QString connectionSummary() const;
    QVariantList detections() const;
    int websocketPort() const;
    bool demoMode() const;

    Q_INVOKABLE void sendMove(int throttle, int turn);
    Q_INVOKABLE void emergencyStop();
    Q_INVOKABLE void releaseEmergencyStop();
    Q_INVOKABLE void setDemoMode(bool enabled);
    Q_INVOKABLE bool saveConnectionSettings(const QString &advertisedHost, const QString &rtspUrl, int websocketPort);

signals:
    void rtspUrlChanged();
    void liveImagePathChanged();
    void connectionSettingsChanged();
    void telemetryChanged();
    void connectionChanged();
    void detectionsChanged();
    void demoModeChanged();
    void websocketServerError(const QString &message);

private slots:
    void onNewWebSocketConnection();
    void onSocketTextMessage(const QString &message);
    void onSocketDisconnected();
    void refreshConnectionState();

private:
    void handleStatus(QWebSocket *socket, const QJsonObject &message);
    void handleDetections(QWebSocket *socket, const QJsonObject &message);
    void sendToRobot(const QJsonObject &message);
    void setDemoTelemetry();
    bool startWebSocketServer(int port);
    static int clampAxis(int value);
    static QString numberText(const QJsonValue &value, const QString &suffix = {});

    QWebSocketServer *m_server = nullptr;
    QSettings m_settings;
    QPointer<QWebSocket> m_robotSocket;
    QPointer<QWebSocket> m_orinSocket;
    QString m_rtspUrl;
    QString m_liveImagePath;
    QString m_advertisedHost;
    int m_websocketPort = 8765;
    QString m_battery = "--";
    QString m_roll = "--";
    QString m_pitch = "--";
    QString m_yaw = "--";
    QStringList m_distances {"--", "--", "--"};
    QVariantList m_detections;
    QDateTime m_lastRobotMessage;
    QDateTime m_lastOrinMessage;
    QTimer m_connectionTimer;
    QTimer m_demoTimer;
    bool m_demoMode = false;
    int m_demoTick = 0;
};
