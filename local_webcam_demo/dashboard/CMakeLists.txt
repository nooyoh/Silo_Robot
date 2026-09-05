cmake_minimum_required(VERSION 3.21)

project(silorobot_dashboard VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_AUTOMOC ON)
set(CMAKE_AUTORCC ON)

find_package(Qt6 6.5 REQUIRED COMPONENTS Core Gui Quick QuickControls2 Multimedia WebSockets)

qt_standard_project_setup(REQUIRES 6.5)

qt_add_executable(silorobot-dashboard
    src/main.cpp
    src/dashboardbackend.cpp
    src/dashboardbackend.h
)

qt_add_qml_module(silorobot-dashboard
    URI SiloRobot.Dashboard
    VERSION 1.0
    QML_FILES
        qml/MainIndustrial.qml
        qml/IndustrialAxis.qml
)

target_link_libraries(silorobot-dashboard
    PRIVATE
        Qt6::Core
        Qt6::Gui
        Qt6::Quick
        Qt6::QuickControls2
        Qt6::Multimedia
        Qt6::WebSockets
)

install(TARGETS silorobot-dashboard)
