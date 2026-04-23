#pragma once

#include <QAbstractListModel>
#include <QJsonArray>
#include <QVariantList>
#include <QVariantMap>

class RecordListModel final : public QAbstractListModel
{
    Q_OBJECT
    Q_PROPERTY(int count READ rowCount NOTIFY countChanged)

public:
    explicit RecordListModel(QObject *parent = nullptr);

    int rowCount(const QModelIndex &parent = QModelIndex()) const override;
    QVariant data(const QModelIndex &index, int role = Qt::DisplayRole) const override;
    QHash<int, QByteArray> roleNames() const override;

    Q_INVOKABLE QVariantMap get(int row) const;
    Q_INVOKABLE void clear();
    void setRows(const QVariantList &rows);
    void setRows(const QJsonArray &rows);

signals:
    void countChanged();

private:
    void rebuildRoles();
    QVariantList m_rows;
    QStringList m_roleOrder;
    QHash<int, QByteArray> m_roles;
};
