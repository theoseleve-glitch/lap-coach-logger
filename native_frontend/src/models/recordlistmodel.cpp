#include "models/recordlistmodel.h"

#include <QSet>

namespace
{
QVariantMap toMap(const QVariant &value)
{
    return value.toMap();
}
}

RecordListModel::RecordListModel(QObject *parent)
    : QAbstractListModel(parent)
{
}

int RecordListModel::rowCount(const QModelIndex &parent) const
{
    if (parent.isValid()) {
        return 0;
    }
    return m_rows.size();
}

QVariant RecordListModel::data(const QModelIndex &index, int role) const
{
    if (!index.isValid() || index.row() < 0 || index.row() >= m_rows.size()) {
        return {};
    }

    const int baseRole = Qt::UserRole + 1;
    const int offset = role - baseRole;
    if (offset < 0 || offset >= m_roleOrder.size()) {
        return {};
    }

    const QVariantMap row = toMap(m_rows.at(index.row()));
    return row.value(m_roleOrder.at(offset));
}

QHash<int, QByteArray> RecordListModel::roleNames() const
{
    return m_roles;
}

QVariantMap RecordListModel::get(int row) const
{
    if (row < 0 || row >= m_rows.size()) {
        return {};
    }
    return toMap(m_rows.at(row));
}

void RecordListModel::clear()
{
    beginResetModel();
    m_rows.clear();
    m_roleOrder.clear();
    m_roles.clear();
    endResetModel();
    emit countChanged();
}

void RecordListModel::setRows(const QVariantList &rows)
{
    beginResetModel();
    m_rows = rows;
    rebuildRoles();
    endResetModel();
    emit countChanged();
}

void RecordListModel::setRows(const QJsonArray &rows)
{
    QVariantList converted;
    converted.reserve(rows.size());
    for (const QJsonValue &value : rows) {
        converted.push_back(value.toObject().toVariantMap());
    }
    setRows(converted);
}

void RecordListModel::rebuildRoles()
{
    m_roleOrder.clear();
    m_roles.clear();

    QSet<QString> seen;
    for (const QVariant &value : m_rows) {
        const QVariantMap row = toMap(value);
        for (auto it = row.constBegin(); it != row.constEnd(); ++it) {
            if (seen.contains(it.key())) {
                continue;
            }
            seen.insert(it.key());
            m_roleOrder.push_back(it.key());
        }
    }

    int role = Qt::UserRole + 1;
    for (const QString &key : m_roleOrder) {
        m_roles.insert(role++, key.toUtf8());
    }
}
