#pragma once

#include "backend/backendgateway.h"

#include <QProcess>

class ProcessBackendGateway final : public BackendGateway
{
    Q_OBJECT

public:
    explicit ProcessBackendGateway(QObject *parent = nullptr);

    void start() override;
    void requestBootstrap() override;
    void sendRequest(const QString &method, const QJsonObject &params = {}) override;

private:
    void handleStdout();
    void handleProcessError();
    void sendEnvelope(const QJsonObject &message);
    QString nextRequestId();

    QProcess m_process;
    QByteArray m_stdoutBuffer;
    quint64 m_nextRequestId = 1;
};
