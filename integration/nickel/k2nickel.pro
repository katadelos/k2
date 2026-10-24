TEMPLATE = lib
TARGET = k2nickel
CONFIG += plugin c++11
QT += core gui widgets network
SOURCES = k2nickel.cpp controlbridge.cpp
HEADERS = controlbridge.h
LIBS += -ldl
QMAKE_LFLAGS += -Wl,-rpath,/usr/local/Kobo -Wl,-rpath,/usr/local/Qt-5.2.1-arm/lib
