#include "dashboardbackend.h"

#include <QCommandLineOption>
#include <QCommandLineParser>
#include <QGuiApplication>
#include <QQmlApplicationEngine>
#include <QQmlContext>
#include <QQuickStyle>

int main(int argc, char *argv[])
{
    QGuiApplication app(argc, argv);
    app.setApplicationName(QStringLiteral("SiloRobot Dashboard"));
    app.setOrganizationName(QStringLiteral("SiloRobot"));
    QQuickStyle::setStyle(QStringLiteral("Basic"));

    QCommandLineParser parser;
    parser.setApplicationDescription(QStringLiteral("SiloRobot RPi4 touch dashboard"));
    parser.addHelpOption();
    QCommandLineOption rtspOption(QStringList {QStringLiteral("r"), QStringLiteral("rtsp")},
        QStringLiteral("RTSP source URL from Jetson Nano B01."), QStringLiteral("url"));
    QCommandLineOption demoOption(QStringList {QStringLiteral("demo")},
        QStringLiteral("Run with local simulated telemetry and a sample detection."));
    QCommandLineOption liveImageOption(QStringList {QStringLiteral("live-image")},
        QStringLiteral("Local webcam demo only: poll this JPEG file as a low-latency preview instead of RTSP."),
        QStringLiteral("path"));
    parser.addOption(rtspOption);
    parser.addOption(demoOption);
    parser.addOption(liveImageOption);
    parser.process(app);

    DashboardBackend backend;
    const QString rtspUrl = parser.isSet(rtspOption)
        ? parser.value(rtspOption)
        : qEnvironmentVariable("DASHBOARD_RTSP_URL");
    if (!rtspUrl.isEmpty())
        backend.setRtspUrl(rtspUrl);
    if (parser.isSet(liveImageOption))
        backend.setLiveImagePath(parser.value(liveImageOption));
    backend.setDemoMode(parser.isSet(demoOption));

    QQmlApplicationEngine engine;
    engine.rootContext()->setContextProperty(QStringLiteral("dashboard"), &backend);
    engine.loadFromModule("SiloRobot.Dashboard", "MainIndustrial");
    if (engine.rootObjects().isEmpty())
        return 1;

    return app.exec();
}
