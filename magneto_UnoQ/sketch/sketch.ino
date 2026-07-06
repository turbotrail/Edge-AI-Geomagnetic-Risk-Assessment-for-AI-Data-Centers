#include <Wire.h>
#include <Adafruit_MMC56x3.h>
#include <Arduino_RouterBridge.h>

Adafruit_MMC5603 mmc;

unsigned long previousMillis = 0;
const int interval = 20;   //50 Hz

void setup()
{
    Bridge.begin();

    Wire.begin();

    if (!mmc.begin(0x30, &Wire))
    {
        while (1);
    }
}

void loop()
{
    if (millis() - previousMillis >= interval)
    {
        previousMillis = millis();

        sensors_event_t mag;

        mmc.getEvent(&mag);

        Bridge.notify(
            "record_magnetometer",
            mag.magnetic.x,
            mag.magnetic.y,
            mag.magnetic.z
        );
    }
}