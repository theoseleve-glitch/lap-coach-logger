#include "backend/mockbackendgateway.h"

#include <QJsonArray>
#include <QUuid>

namespace
{
QJsonObject metric(const QString &label, const QString &value, const QString &tone = QStringLiteral("neutral"))
{
    return {
        {QStringLiteral("label"), label},
        {QStringLiteral("value"), value},
        {QStringLiteral("tone"), tone},
    };
}
}

MockBackendGateway::MockBackendGateway(QObject *parent)
    : BackendGateway(parent)
{
    m_tickTimer.setInterval(1000);
    connect(&m_tickTimer, &QTimer::timeout, this, [this]() {
        ++m_tick;
        emitShellState();
        emitLiveState();
    });
}

void MockBackendGateway::start()
{
    emit connectionStateChanged(true, QStringLiteral("Mock backend"));
    emitBootstrap();
    m_tickTimer.start();
}

void MockBackendGateway::requestBootstrap()
{
    emitBootstrap();
}

void MockBackendGateway::sendRequest(const QString &method, const QJsonObject &params)
{
    Q_UNUSED(params)
    if (method == QStringLiteral("service.startMonitoring")) {
        m_monitoringActive = true;
        emitShellState();
        return;
    }
    if (method == QStringLiteral("service.stopMonitoring")) {
        m_monitoringActive = false;
        emitShellState();
        return;
    }
    if (method.startsWith(QStringLiteral("overlay."))) {
        emitOverlayState();
        return;
    }
    emit responseReceived(QUuid::createUuid().toString(QUuid::WithoutBraces), true, {}, {});
}

void MockBackendGateway::emitBootstrap()
{
    emitShellState();
    emitDashboardState();
    emitLiveState();
    emitLogsState();
    emitHistoryState();
    emitReviewState();
    emitOverlayState();
}

void MockBackendGateway::emitShellState()
{
    emit eventReceived(
        QStringLiteral("shell/state"),
        QJsonObject{
            {QStringLiteral("screenTitle"), QStringLiteral("LAP COACH")},
            {QStringLiteral("status"), m_monitoringActive ? QStringLiteral("Recording") : QStringLiteral("Paused")},
            {QStringLiteral("statusDetail"), m_monitoringActive ? QStringLiteral("ACC / Race / Lap 7") : QStringLiteral("Monitoring paused")},
            {QStringLiteral("connected"), true},
            {QStringLiteral("connectionLabel"), QStringLiteral("Bridge connected")},
            {QStringLiteral("monitoringActive"), m_monitoringActive},
            {QStringLiteral("simulator"), QStringLiteral("ACC")},
            {QStringLiteral("sessionType"), QStringLiteral("Race")},
            {QStringLiteral("liveState"), m_monitoringActive ? QStringLiteral("Live telemetry") : QStringLiteral("Standby")},
        });
}

void MockBackendGateway::emitDashboardState()
{
    emit eventReceived(
        QStringLiteral("screen/dashboard"),
        QJsonObject{
            {QStringLiteral("metrics"),
             QJsonArray{metric(QStringLiteral("Speed"), QStringLiteral("214 km/h")),
                        metric(QStringLiteral("Gear"), QStringLiteral("5")),
                        metric(QStringLiteral("RPM"), QStringLiteral("7125"), QStringLiteral("accent")),
                        metric(QStringLiteral("Fuel"), QStringLiteral("48.6 L"))}},
            {QStringLiteral("operations"),
             QJsonObject{{QStringLiteral("profile"), QStringLiteral("ACC GT3 / Ferrari 296")},
                         {QStringLiteral("rawCapture"), QStringLiteral("Armed")},
                         {QStringLiteral("sync"), QStringLiteral("Online")},
                         {QStringLiteral("sim"), QStringLiteral("ACC")}}},
            {QStringLiteral("coaching"),
             QJsonArray{QJsonObject{{QStringLiteral("label"), QStringLiteral("Trail braking")},
                                    {QStringLiteral("message"), QStringLiteral("Brake release is 6% later than reference")}},
                        QJsonObject{{QStringLiteral("label"), QStringLiteral("Corner exit")},
                                    {QStringLiteral("message"), QStringLiteral("Throttle pickup is stable and improving")}}}},
        });
}

void MockBackendGateway::emitLiveState()
{
    emit eventReceived(
        QStringLiteral("screen/live"),
        QJsonObject{
            {QStringLiteral("metrics"),
             QJsonArray{metric(QStringLiteral("Speed"), QString::number(206 + (m_tick % 8)) + QStringLiteral(" km/h")),
                        metric(QStringLiteral("Throttle"), QStringLiteral("81%")),
                        metric(QStringLiteral("Brake"), QStringLiteral("04%")),
                        metric(QStringLiteral("Steering"), QStringLiteral("-12.4°"))}},
            {QStringLiteral("health"),
             QJsonArray{QJsonObject{{QStringLiteral("label"), QStringLiteral("Stream")}, {QStringLiteral("value"), QStringLiteral("OK")}},
                        QJsonObject{{QStringLiteral("label"), QStringLiteral("Update rate")}, {QStringLiteral("value"), QStringLiteral("10.0 Hz")}},
                        QJsonObject{{QStringLiteral("label"), QStringLiteral("Staleness")}, {QStringLiteral("value"), QStringLiteral("0.10 s")}}}},
        });
}

void MockBackendGateway::emitLogsState()
{
    emit eventReceived(
        QStringLiteral("screen/logs"),
        QJsonObject{
            {QStringLiteral("rows"),
             QJsonArray{
                 QJsonObject{{QStringLiteral("time"), QStringLiteral("16:03:21")}, {QStringLiteral("severity"), QStringLiteral("INFO")}, {QStringLiteral("subsystem"), QStringLiteral("session")}, {QStringLiteral("module"), QStringLiteral("lap_coach_logger.core.session_coordinator")}, {QStringLiteral("message"), QStringLiteral("Valid session detected on ACC")}},
                 QJsonObject{{QStringLiteral("time"), QStringLiteral("16:03:24")}, {QStringLiteral("severity"), QStringLiteral("INFO")}, {QStringLiteral("subsystem"), QStringLiteral("overlay")}, {QStringLiteral("module"), QStringLiteral("lap_coach_logger.overlays.runtime")}, {QStringLiteral("message"), QStringLiteral("Blind Spot mounted on Broadcast layout")}},
                 QJsonObject{{QStringLiteral("time"), QStringLiteral("16:03:28")}, {QStringLiteral("severity"), QStringLiteral("WARN")}, {QStringLiteral("subsystem"), QStringLiteral("stream")}, {QStringLiteral("module"), QStringLiteral("lap_coach_logger.ui.desktop.service")}, {QStringLiteral("message"), QStringLiteral("Live stream staleness approaching threshold")}},
             }},
        });
}

void MockBackendGateway::emitHistoryState()
{
    emit eventReceived(
        QStringLiteral("screen/history"),
        QJsonObject{
            {QStringLiteral("rows"),
             QJsonArray{
                 QJsonObject{{QStringLiteral("date"), QStringLiteral("2026-04-03 15:58")}, {QStringLiteral("sim"), QStringLiteral("ACC")}, {QStringLiteral("track"), QStringLiteral("Spa-Francorchamps")}, {QStringLiteral("car"), QStringLiteral("Ferrari 296 GT3")}, {QStringLiteral("duration"), QStringLiteral("22m")}, {QStringLiteral("laps"), QStringLiteral("14")}, {QStringLiteral("quality"), QStringLiteral("Ready")}},
                 QJsonObject{{QStringLiteral("date"), QStringLiteral("2026-04-03 14:42")}, {QStringLiteral("sim"), QStringLiteral("LMU")}, {QStringLiteral("track"), QStringLiteral("Le Mans")}, {QStringLiteral("car"), QStringLiteral("Porsche 963")}, {QStringLiteral("duration"), QStringLiteral("18m")}, {QStringLiteral("laps"), QStringLiteral("9")}, {QStringLiteral("quality"), QStringLiteral("Review")}},
             }},
        });
}

void MockBackendGateway::emitReviewState()
{
    emit eventReceived(
        QStringLiteral("screen/review"),
        QJsonObject{
            {QStringLiteral("title"), QStringLiteral("Session Review")},
            {QStringLiteral("status"), QStringLiteral("Ready")},
            {QStringLiteral("summary"), QStringLiteral("Clean GT3 session with stable telemetry coverage and one setup recommendation.")},
            {QStringLiteral("warnings"), QJsonArray{QStringLiteral("Minor data freeze during pit entry"), QStringLiteral("Two tyre temperature samples interpolated")}},
        });
}

void MockBackendGateway::emitOverlayState()
{
    emit eventReceived(
        QStringLiteral("screen/overlay"),
        QJsonObject{
            {QStringLiteral("selection"), QJsonObject{{QStringLiteral("selectedOverlayId"), QStringLiteral("blind_spot")}, {QStringLiteral("selectedCategory"), QStringLiteral("Awareness")}, {QStringLiteral("selectedLayoutId"), QStringLiteral("broadcast")}}},
            {QStringLiteral("categories"),
             QJsonArray{
                 QJsonObject{{QStringLiteral("category"), QStringLiteral("All")}, {QStringLiteral("label"), QStringLiteral("All")}, {QStringLiteral("count"), 14}, {QStringLiteral("selected"), false}},
                 QJsonObject{{QStringLiteral("category"), QStringLiteral("Awareness")}, {QStringLiteral("label"), QStringLiteral("Awareness")}, {QStringLiteral("count"), 5}, {QStringLiteral("selected"), true}},
                 QJsonObject{{QStringLiteral("category"), QStringLiteral("Timing")}, {QStringLiteral("label"), QStringLiteral("Timing")}, {QStringLiteral("count"), 4}, {QStringLiteral("selected"), false}},
             }},
            {QStringLiteral("overlays"),
             QJsonArray{
                 QJsonObject{{QStringLiteral("overlayId"), QStringLiteral("blind_spot")}, {QStringLiteral("displayName"), QStringLiteral("Blind Spot Radar")}, {QStringLiteral("category"), QStringLiteral("Awareness")}, {QStringLiteral("status"), QStringLiteral("active")}, {QStringLiteral("active"), true}, {QStringLiteral("selected"), true}, {QStringLiteral("favorite"), true}, {QStringLiteral("locked"), false}, {QStringLiteral("compatibility"), QStringLiteral("ACC / LMU / iRacing")}},
                 QJsonObject{{QStringLiteral("overlayId"), QStringLiteral("delta_bar")}, {QStringLiteral("displayName"), QStringLiteral("Delta Bar Pro")}, {QStringLiteral("category"), QStringLiteral("Timing")}, {QStringLiteral("status"), QStringLiteral("installed")}, {QStringLiteral("active"), false}, {QStringLiteral("selected"), false}, {QStringLiteral("favorite"), false}, {QStringLiteral("locked"), false}, {QStringLiteral("compatibility"), QStringLiteral("ACC / iRacing")}},
                 QJsonObject{{QStringLiteral("overlayId"), QStringLiteral("strategy_hud")}, {QStringLiteral("displayName"), QStringLiteral("Strategy HUD")}, {QStringLiteral("category"), QStringLiteral("Strategy")}, {QStringLiteral("status"), QStringLiteral("locked")}, {QStringLiteral("active"), false}, {QStringLiteral("selected"), false}, {QStringLiteral("favorite"), false}, {QStringLiteral("locked"), true}, {QStringLiteral("compatibility"), QStringLiteral("Premium")}},
             }},
            {QStringLiteral("layouts"),
             QJsonArray{
                 QJsonObject{{QStringLiteral("layoutId"), QStringLiteral("broadcast")}, {QStringLiteral("displayName"), QStringLiteral("Broadcast")}, {QStringLiteral("selected"), true}, {QStringLiteral("active"), true}, {QStringLiteral("favorite"), true}},
                 QJsonObject{{QStringLiteral("layoutId"), QStringLiteral("qualifying")}, {QStringLiteral("displayName"), QStringLiteral("Qualifying")}, {QStringLiteral("selected"), false}, {QStringLiteral("active"), false}, {QStringLiteral("favorite"), false}},
                 QJsonObject{{QStringLiteral("layoutId"), QStringLiteral("night_stint")}, {QStringLiteral("displayName"), QStringLiteral("Night Stint Analysis")}, {QStringLiteral("selected"), false}, {QStringLiteral("active"), false}, {QStringLiteral("favorite"), false}},
             }},
            {QStringLiteral("selectedOverlay"),
             QJsonObject{
                 {QStringLiteral("displayName"), QStringLiteral("Blind Spot Radar")},
                 {QStringLiteral("shortDescription"), QStringLiteral("Side proximity awareness for close traffic and multi-class racing.")},
                 {QStringLiteral("category"), QStringLiteral("Awareness")},
                 {QStringLiteral("active"), true},
                 {QStringLiteral("favorite"), true},
                 {QStringLiteral("installed"), true},
                 {QStringLiteral("compatibility"), QStringLiteral("ACC / LMU / iRacing")},
                 {QStringLiteral("previewMode"), QStringLiteral("Live layout preview")},
                 {QStringLiteral("actions"),
                  QJsonArray{
                      QJsonObject{{QStringLiteral("actionId"), QStringLiteral("activate")}, {QStringLiteral("label"), QStringLiteral("Activate")}, {QStringLiteral("enabled"), false}},
                      QJsonObject{{QStringLiteral("actionId"), QStringLiteral("deactivate")}, {QStringLiteral("label"), QStringLiteral("Deactivate")}, {QStringLiteral("enabled"), true}},
                      QJsonObject{{QStringLiteral("actionId"), QStringLiteral("start_preview")}, {QStringLiteral("label"), QStringLiteral("Preview")}, {QStringLiteral("enabled"), true}},
                  }},
                 {QStringLiteral("settingsSections"),
                  QJsonArray{
                      QJsonObject{{QStringLiteral("sectionKey"), QStringLiteral("overlay")},
                                  {QStringLiteral("label"), QStringLiteral("Overlay")},
                                  {QStringLiteral("fields"),
                                   QJsonArray{
                                       QJsonObject{{QStringLiteral("fieldKey"), QStringLiteral("enabled")}, {QStringLiteral("label"), QStringLiteral("Active in layout")}, {QStringLiteral("kind"), QStringLiteral("bool")}, {QStringLiteral("currentValue"), true}, {QStringLiteral("description"), QStringLiteral("Show this overlay in the selected layout.")}},
                                       QJsonObject{{QStringLiteral("fieldKey"), QStringLiteral("favorite")}, {QStringLiteral("label"), QStringLiteral("Favorite")}, {QStringLiteral("kind"), QStringLiteral("bool")}, {QStringLiteral("currentValue"), true}, {QStringLiteral("description"), QStringLiteral("Pin for faster access in the browser.")}},
                                   }}},
                      QJsonObject{{QStringLiteral("sectionKey"), QStringLiteral("placement")},
                                  {QStringLiteral("label"), QStringLiteral("Placement")},
                                  {QStringLiteral("fields"),
                                   QJsonArray{
                                       QJsonObject{{QStringLiteral("fieldKey"), QStringLiteral("scale")}, {QStringLiteral("label"), QStringLiteral("Scale")}, {QStringLiteral("kind"), QStringLiteral("float")}, {QStringLiteral("currentValue"), 100}, {QStringLiteral("unit"), QStringLiteral("%")}},
                                       QJsonObject{{QStringLiteral("fieldKey"), QStringLiteral("anchor")}, {QStringLiteral("label"), QStringLiteral("Anchor")}, {QStringLiteral("kind"), QStringLiteral("enum")}, {QStringLiteral("currentValue"), QStringLiteral("right")}, {QStringLiteral("options"),
                                                    QJsonArray{
                                                        QJsonObject{{QStringLiteral("value"), QStringLiteral("left")}, {QStringLiteral("label"), QStringLiteral("Left")}},
                                                        QJsonObject{{QStringLiteral("value"), QStringLiteral("right")}, {QStringLiteral("label"), QStringLiteral("Right")}},
                                                        QJsonObject{{QStringLiteral("value"), QStringLiteral("top_right")}, {QStringLiteral("label"), QStringLiteral("Top right")}},
                                                    }}}},
                                   }}},
                  }},
             }},
        });
}
