#pragma once

#include <QDateTime>
#include <QJsonObject>
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
    Q_PROPERTY(QString advertisedHost READ advertisedHost NOTIFY connectionSettingsChanged)
    Q_PROPERTY(QString dashboardEndpoint READ dashboardEndpoint NOTIFY connectionSettingsChanged)
    Q_PROPERTY(QString battery READ battery NOTIFY telemetryChanged)
    Q_PROPERTY(QString roll READ roll NOTIFY telemetryChanged)
    Q_PROPERTY(QString pitch READ pitch NOTIFY telemetryChanged)
    Q_PROPERTY(QString yaw READ yaw NOTIFY telemetryChanged)
    Q_PROPERTY(QStringList distances READ distances NOTIFY telemetryChanged)
    Q_PROPERTY(QString distanceUnit READ distanceUnit NOTIFY telemetryChanged)
    Q_PROPERTY(QString distanceMean READ distanceMean NOTIFY telemetryChanged)
    Q_PROPERTY(QString distanceSpread READ distanceSpread NOTIFY telemetryChanged)
    Q_PROPERTY(QString safetyState READ safetyState NOTIFY safetyChanged)
    Q_PROPERTY(QStringList safetyReasons READ safetyReasons NOTIFY safetyChanged)
    Q_PROPERTY(bool safetyLatched READ safetyLatched NOTIFY safetyChanged)
    Q_PROPERTY(bool safetyArmed READ safetyArmed NOTIFY safetyChanged)
    Q_PROPERTY(QString releaseFeedback READ releaseFeedback NOTIFY safetyChanged)
    Q_PROPERTY(QVariantList recentRecords READ recentRecords NOTIFY recordsChanged)
    Q_PROPERTY(QString recordFeedback READ recordFeedback NOTIFY recordsChanged)
    Q_PROPERTY(QString missionMode READ missionMode NOTIFY missionChanged)
    Q_PROPERTY(QString missionState READ missionState NOTIFY missionChanged)
    Q_PROPERTY(QString planId READ planId NOTIFY missionChanged)
    Q_PROPERTY(int currentWaypoint READ currentWaypoint NOTIFY missionChanged)
    Q_PROPERTY(int totalWaypoints READ totalWaypoints NOTIFY missionChanged)
    Q_PROPERTY(double coverageRatio READ coverageRatio NOTIFY missionChanged)
    Q_PROPERTY(bool planReady READ planReady NOTIFY missionChanged)
    Q_PROPERTY(QString planOrientation READ planOrientation NOTIFY missionChanged)
    Q_PROPERTY(double planEstimatedLength READ planEstimatedLength NOTIFY missionChanged)
    Q_PROPERTY(int planTurnCount READ planTurnCount NOTIFY missionChanged)
    Q_PROPERTY(QVariantList planWaypoints READ planWaypoints NOTIFY missionChanged)
    Q_PROPERTY(QVariantList planCandidates READ planCandidates NOTIFY missionChanged)
    Q_PROPERTY(bool poseValid READ poseValid NOTIFY missionChanged)
    Q_PROPERTY(double poseX READ poseX NOTIFY missionChanged)
    Q_PROPERTY(double poseY READ poseY NOTIFY missionChanged)
    Q_PROPERTY(double poseTheta READ poseTheta NOTIFY missionChanged)
    Q_PROPERTY(double planWidth READ planWidth NOTIFY missionChanged)
    Q_PROPERTY(double planHeight READ planHeight NOTIFY missionChanged)
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
    QString advertisedHost() const;
    QString dashboardEndpoint() const;
    QString battery() const;
    QString roll() const;
    QString pitch() const;
    QString yaw() const;
    QStringList distances() const;
    QString distanceUnit() const;
    QString distanceMean() const;
    QString distanceSpread() const;
    QString safetyState() const;
    QStringList safetyReasons() const;
    bool safetyLatched() const;
    bool safetyArmed() const;
    QString releaseFeedback() const;
    QVariantList recentRecords() const;
    QString recordFeedback() const;
    QString missionMode() const;
    QString missionState() const;
    QString planId() const;
    int currentWaypoint() const;
    int totalWaypoints() const;
    double coverageRatio() const;
    bool planReady() const;
    QString planOrientation() const;
    double planEstimatedLength() const;
    int planTurnCount() const;
    QVariantList planWaypoints() const;
    QVariantList planCandidates() const;
    bool poseValid() const;
    double poseX() const;
    double poseY() const;
    double poseTheta() const;
    double planWidth() const;
    double planHeight() const;
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
    Q_INVOKABLE QString captureStagingPath();
    Q_INVOKABLE bool saveInspectionRecord(const QString &stagingImagePath,
                                           const QString &errorMessage = {},
                                           const QString &trigger = {});
    Q_INVOKABLE QVariantList loadAllRecords();
    Q_INVOKABLE bool deleteRecord(const QString &date, const QString &recordId);
    Q_INVOKABLE void requestRoutePlan(double width, double height, double scanWidth,
                                      double overlapRatio, double safetyMargin,
                                      const QString &startCorner);
    Q_INVOKABLE void sendAutonomyCommand(const QString &type);
    Q_INVOKABLE void setOnScreenKeyboardVisible(bool visible);
    Q_INVOKABLE void quitApplication();

signals:
    void rtspUrlChanged();
    void connectionSettingsChanged();
    void telemetryChanged();
    void safetyChanged();
    void recordsChanged();
    void missionChanged();
    void connectionChanged();
    void detectionsChanged();
    void demoModeChanged();
    void websocketServerError(const QString &message);
    void safetyRecordRequested(const QString &trigger);

private slots:
    void onNewWebSocketConnection();
    void onSocketTextMessage(const QString &message);
    void onSocketDisconnected();
    void refreshConnectionState();

private:
    void handleStatus(QWebSocket *socket, const QJsonObject &message);
    void handleDetections(QWebSocket *socket, const QJsonObject &message);
    void updateSafety(const QJsonObject &message);
    void sendToRobot(const QJsonObject &message);
    void setDemoTelemetry();
    bool startWebSocketServer(int port);
    static int clampAxis(int value);
    static QString numberText(const QJsonValue &value, const QString &suffix = {}, bool zeroUnavailable = false);
    static QString reasonText(const QString &reason);

    QWebSocketServer *m_server = nullptr;
    QSettings m_settings;
    QPointer<QWebSocket> m_robotSocket;
    QPointer<QWebSocket> m_orinSocket;
    QString m_rtspUrl;
    QString m_advertisedHost;
    int m_websocketPort = 8765;
    QString m_battery = "--";
    QString m_roll = "--";
    QString m_pitch = "--";
    QString m_yaw = "--";
    QStringList m_distances {"--", "--", "--"};
    QString m_distanceUnit = QStringLiteral("REL");
    QString m_distanceMean = QStringLiteral("--");
    QString m_distanceSpread = QStringLiteral("--");
    QString m_safetyState = QStringLiteral("OFFLINE");
    QStringList m_safetyReasons {QStringLiteral("sensor_waiting")};
    bool m_safetyLatched = true;
    bool m_safetyArmed = false;
    QString m_releaseFeedback;
    QVariantList m_recentRecords;
    QString m_recordFeedback;
    bool m_releasePending = false;
    QString m_missionMode = QStringLiteral("MANUAL");
    QString m_missionState = QStringLiteral("IDLE");
    QString m_planId;
    int m_currentWaypoint = 0;
    int m_totalWaypoints = 0;
    double m_coverageRatio = 0.0;
    bool m_planReady = false;
    QString m_planOrientation;
    double m_planEstimatedLength = 0.0;
    int m_planTurnCount = 0;
    QVariantList m_planWaypoints;
    QVariantList m_planCandidates;
    bool m_poseValid = false;
    double m_poseX = 0.0;
    double m_poseY = 0.0;
    double m_poseTheta = 0.0;
    double m_planWidth = 0.0;
    double m_planHeight = 0.0;
    QVariantList m_detections;
    QJsonObject m_lastStatus;
    QString m_poseSource = QStringLiteral("UNAVAILABLE");
    bool m_receivedSafetyState = false;
    QDateTime m_lastRobotMessage;
    QDateTime m_lastOrinMessage;
    QTimer m_connectionTimer;
    QTimer m_demoTimer;
    bool m_demoMode = false;
    int m_demoTick = 0;
};
