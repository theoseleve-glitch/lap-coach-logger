#include "backend/processbackendgateway.h"

#include <QCoreApplication>
#include <QJsonDocument>
#include <QProcessEnvironment>

BackendGateway::BackendGateway(QObject *parent)
    : QObject(parent)
{
}

ProcessBackendGateway::ProcessBackendGateway(QObject *parent)
    : BackendGateway(parent)
{
    connect(&m_process, &QProcess::readyReadStandardOutput, this, &ProcessBackendGateway::handleStdout);
    connect(&m_process, &QProcess::errorOccurred, this, [this](QProcess::ProcessError) { handleProcessError(); });
    connect(&m_process, &QProcess::started, this, [this]() {
        emit connectionStateChanged(true, QStringLiteral("Python backend bridge started"));
        requestBootstrap();
    });
    connect(&m_process, &QProcess::finished, this, [this](int, QProcess::ExitStatus) {
        emit connectionStateChanged(false, QStringLiteral("Python backend bridge stopped"));
    });
}

void ProcessBackendGateway::start()
{
    const QProcessEnvironment env = QProcessEnvironment::systemEnvironment();
    const QString program = env.value(QStringLiteral("LAP_COACH_NATIVE_BACKEND_PROGRAM"), QStringLiteral("python"));
    QStringList arguments;
    const QString argString = env.value(QStringLiteral("LAP_COACH_NATIVE_BACKEND_ARGS"));
    if (!argString.trimmed().isEmpty()) {
        arguments = QProcess::splitCommand(argString);
    } else {
        arguments << QStringLiteral("-m") << QStringLiteral("lap_coach_logger.native_bridge");
    }

    m_process.setProcessChannelMode(QProcess::SeparateChannels);
    m_process.setWorkingDirectory(QCoreApplication::applicationDirPath());
    m_process.start(program, arguments);
}

void ProcessBackendGateway::requestBootstrap()
{
    sendRequest(QStringLiteral("bootstrap"));
}

void ProcessBackendGateway::sendRequest(const QString &method, const QJsonObject &params)
{
    sendEnvelope(
        QJsonObject{
            {QStringLiteral("type"), QStringLiteral("request")},
            {QStringLiteral("id"), nextRequestId()},
            {QStringLiteral("method"), method},
            {QStringLiteral("params"), params},
        });
}

void ProcessBackendGateway::handleStdout()
{
    m_stdoutBuffer.append(m_process.readAllStandardOutput());
    forever {
        const int newlineIndex = m_stdoutBuffer.indexOf('\n');
        if (newlineIndex < 0) {
            break;
        }

        const QByteArray line = m_stdoutBuffer.left(newlineIndex).trimmed();
        m_stdoutBuffer.remove(0, newlineIndex + 1);
        if (line.isEmpty()) {
            continue;
        }

        const QJsonDocument doc = QJsonDocument::fromJson(line);
        if (!doc.isObject()) {
            continue;
        }

        const QJsonObject payload = doc.object();
        const QString type = payload.value(QStringLiteral("type")).toString();
        if (type == QStringLiteral("event")) {
            emit eventReceived(
                payload.value(QStringLiteral("event")).toString(),
                payload.value(QStringLiteral("payload")).toObject());
        } else if (type == QStringLiteral("response")) {
            emit responseReceived(
                payload.value(QStringLiteral("id")).toString(),
                payload.value(QStringLiteral("ok")).toBool(),
                payload.value(QStringLiteral("result")),
                payload.value(QStringLiteral("error")).toString());
        }
    }
}

void ProcessBackendGateway::handleProcessError()
{
    emit connectionStateChanged(false, m_process.errorString());
}

void ProcessBackendGateway::sendEnvelope(const QJsonObject &message)
{
    if (m_process.state() != QProcess::Running) {
        emit connectionStateChanged(false, QStringLiteral("Python backend bridge is not running"));
        return;
    }
    QByteArray encoded = QJsonDocument(message).toJson(QJsonDocument::Compact);
    encoded.append('\n');
    m_process.write(encoded);
    m_process.flush();
}

QString ProcessBackendGateway::nextRequestId()
{
    return QString::number(m_nextRequestId++);
}
