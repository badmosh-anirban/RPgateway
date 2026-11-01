#pragma once

#include <stdint.h>

constexpr uint8_t PROTOCOL_VERSION = 1;

enum PacketType : uint8_t {
    PKT_SYNC = 1,
    PKT_DATA = 2
};

struct __attribute__((packed)) PacketHeader {
    uint8_t version;
    uint8_t type;
    uint8_t nodeId;
    uint8_t gatewayId;
    uint16_t sequence;
    uint32_t frameNumber;
    uint16_t payloadLength;
};

struct __attribute__((packed)) SyncPayload {
    uint16_t slotDurationMs;
    uint16_t guardTimeMs;
    uint8_t nodeCount;
};

struct __attribute__((packed)) SensorPayload {
    int16_t temperatureX10;
    uint32_t pressurePa;
    uint16_t gasAdc;
    uint8_t flame;
    uint8_t vibration;
    int16_t accelX;
    int16_t accelY;
    int16_t accelZ;
    uint32_t uptimeSeconds;
};

struct __attribute__((packed)) DataPacket {
    PacketHeader header;
    SensorPayload payload;
};

struct __attribute__((packed)) SyncPacket {
    PacketHeader header;
    SyncPayload payload;
};