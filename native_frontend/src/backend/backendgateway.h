#pragma once

#include <QObject>
#include <QJsonObject>
#include <QJsonValue>

class BackendGateway : public QObject
{
    Q_OBJECT

public:
    explicit BackendGateway(QObject *parent = nullptr);
    ~BackendGateway() override = default;

    virtual void start() = 0;
    virtual void requestBootstrap() = 0;
    virtual void sendRequest(const QString &method, const QJsonObject &params = {}) = 0;

signals:
    void connectionStateChanged(bool connected, const QString &detail);
    void eventReceived(const QString &eventName, const QJsonObject &payload);
    void responseReceived(const QString &requestId, bool ok, const QJsonValue &result, const QString &error);
};
