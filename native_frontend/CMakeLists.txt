cmake_minimum_required(VERSION 3.24)

project(LapCoachDesktopNative VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_AUTOMOC ON)
set(CMAKE_AUTORCC ON)
set(CMAKE_AUTOUIC ON)

find_package(Qt6 6.5 REQUIRED COMPONENTS Core Gui Qml Quick QuickControls2)

qt_standard_project_setup(REQUIRES 6.5)

set_source_files_properties(
    qml/theme/Theme.qml
    PROPERTIES QT_QML_SINGLETON_TYPE TRUE
)

qt_add_executable(LapCoachDesktopNative
    src/main.cpp
    src/app/applicationcontroller.cpp
    src/backend/mockbackendgateway.cpp
    src/backend/processbackendgateway.cpp
    src/models/recordlistmodel.cpp
)

target_sources(LapCoachDesktopNative PRIVATE
    src/app/applicationcontroller.h
    src/backend/backendgateway.h
    src/backend/mockbackendgateway.h
    src/backend/processbackendgateway.h
    src/models/recordlistmodel.h
)

qt_add_qml_module(LapCoachDesktopNative
    URI LapCoachDesktop
    VERSION 1.0
    QML_FILES
        qml/Main.qml
        qml/theme/Theme.qml
        qml/components/SurfacePane.qml
        qml/components/ToolbarButton.qml
        qml/components/StatusBadge.qml
        qml/components/SectionHeader.qml
        qml/components/InspectorGroup.qml
        qml/components/MetricCell.qml
        qml/components/OverlayCanvas.qml
        qml/components/LayoutTabs.qml
        qml/screens/DashboardScreen.qml
        qml/screens/LiveScreen.qml
        qml/screens/LogsScreen.qml
        qml/screens/HistoryScreen.qml
        qml/screens/OverlayScreen.qml
        qml/screens/ReviewScreen.qml
)

target_include_directories(LapCoachDesktopNative PRIVATE src)

target_link_libraries(LapCoachDesktopNative
    PRIVATE
        Qt6::Core
        Qt6::Gui
        Qt6::Qml
        Qt6::Quick
        Qt6::QuickControls2
)

set_target_properties(LapCoachDesktopNative PROPERTIES
    WIN32_EXECUTABLE TRUE
    MACOSX_BUNDLE TRUE
)
