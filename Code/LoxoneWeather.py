#!/usr/bin/env python
# -*- coding: utf-8 -*-

import SocketServer
import SimpleHTTPServer
import urllib
import json
import sys
import datetime
import requests
import urlparse
import os
import pytz

# HTTP Proxy Server for the Loxone Weather Service
# (Can be run on a Raspberry Pi)

# You need a private DNS server, which the Miniserver uses. That DNS server needs
# to forward `weather.loxone.com` to this server!

# Visit https://darksky.net to setup an account and use an evaluation account
# (1000 requests per day is more than enough for your server)
# The 'SECRET KEY' needs to be added:
OPENWEATHERMAP_API_KEY = os.environ.get("OPENWEATHERMAP_API_KEY")
LANGUAGE = os.environ.get("LANGUAGE", "en")
UNITS = os.environ.get("UNITS", "metric")
licenseExpiryDate = datetime.datetime(2049, 12, 31, 0, 0)
LOXONE_WEATHER_SERVICE_PORT = 6066


def downloadReport(longitude, latitude, asl):

    r = requests.get('https://api.openweathermap.org/data/2.5/onecall?appid=' +
                     OPENWEATHERMAP_API_KEY+'&lang={lang}&units={units}&lon={lon:.3f}&lat={lat:.2f}'.format(lon=longitude, lat=latitude, lang=LANGUAGE, units=UNITS))
    if r.status_code == 200:
        ret = r.content
    else:
        print 'Error %d' % (r.status_code)
        ret = None
    return ret

# Generate an icon for Loxone based on the Meteoblue picto-codes
# <https://content.meteoblue.com/en/help/standards/symbols-and-pictograms>
#  1	Clear, cloudless sky (Loxone: Wolkenlos)
#  2	Clear, few cirrus (Loxone: Wolkenlos)
#  3	Clear with cirrus (Loxone: Heiter)
#  4	Clear with few low clouds (Loxone: Heiter)
#  5	Clear with few low clouds and few cirrus (Loxone: Heiter)
#  6	Clear with few low clouds and cirrus (Loxone: Heiter)
#  7	Partly cloudy (Loxone: Heiter)
#  8	Partly cloudy and few cirrus (Loxone: Heiter)
#  9	Partly cloudy and cirrus (Loxone: Wolkig)
# 10	Mixed with some thunderstorm clouds possible (Loxone: Wolkig)
# 11	Mixed with few cirrus with some thunderstorm clouds possible (Loxone: Wolkig)
# 12	Mixed with cirrus and some thunderstorm clouds possible (Loxone: Wolkig)
# 13	Clear but hazy (Loxone: Wolkenlos)
# 14	Clear but hazy with few cirrus (Loxone: Heiter)
# 15	Clear but hazy with cirrus (Loxone: Heiter)
# 16	Fog/low stratus clouds (Loxone: Nebel)
# 17	Fog/low stratus clouds with few cirrus (Loxone: Nebel)
# 18	Fog/low stratus clouds with cirrus (Loxone: Nebel)
# 19	Mostly cloudy (Loxone: Stark bewölkt)
# 20	Mostly cloudy and few cirrus (Loxone: Stark bewölkt)
# 21	Mostly cloudy and cirrus (Loxone: Stark bewölkt)
# 22	Overcast (Loxone: Bedeckt)
# 23	Overcast with rain (Loxone: Regen)
# 24	Overcast with snow (Loxone: Schneefall)
# 25	Overcast with heavy rain (Loxone: Starker Regen)
# 26	Overcast with heavy snow (Loxone: Starker Schneefall)
# 27	Rain, thunderstorms likely (Loxone: Kräftiges Gewitter)
# 28	Light rain, thunderstorms likely (Loxone: Gewitter)
# 29	Storm with heavy snow (Loxone: Starker Schneeschauer)
# 30	Heavy rain, thunderstorms likely (Loxone: Kräftiges Gewitter)
# 31	Mixed with showers (Loxone: Leichter Regenschauer)
# 32	Mixed with snow showers (Loxone: Leichter Schneeschauer)
# 33	Overcast with light rain (Loxone: Leichter Regen)
# 34	Overcast with light snow (Loxone: Leichter Schneeschauer)
# 35	Overcast with mixture of snow and rain (Loxone: Schneeregen)


def loxoneWeatherIcon(weatherReportHourly):
    weather = weatherReportHourly["weather"]

    iconDarksky = weather[0]['main']
    if iconDarksky == 'clear-day' or iconDarksky == 'clear-night':
        iconID = 1  # wolkenlos
    elif iconDarksky == 'rain':
        iconID = 23  # Regen
    elif iconDarksky == 'snow':
        iconID = 24  # Schneefall
    elif iconDarksky == 'sleet':
        iconID = 35  # Schneeregen
#    elif iconDarksky == 'wind':
#        pass
    elif iconDarksky == 'fog':
        iconID = 16  # Nebel
    elif iconDarksky == 'cloudy':
        iconID = 7  # Wolkig
    elif iconDarksky == 'partly-cloudy-day' or iconDarksky == 'partly-cloudy-night':
        iconID = 7  # Wolkig
    elif iconDarksky == 'hail':
        iconID = 35  # Schneeregen
    elif iconDarksky == 'thunderstorm':
        iconID = 28  # Gewitter
#    elif iconDarksky == 'tornado':
#        iconID = 29 # kräftiges Gewitter
    else:
        iconID = 7  # Wolkig

    # fix the cloud cover icon
    if iconID == 7:
        cloudCover = weatherReportHourly['clouds']
        if cloudCover < 0.125:
            iconID = 1  # Wolkenlos und sonnig
        elif cloudCover < 0.5:
            iconID = 3  # Heiter und leicht bewölkt
        elif cloudCover < 0.75:
            iconID = 9  # bewölkt bis stark bewölkt
        elif cloudCover < 0.875:
            iconID = 19  # Stark bewölkt
        else:
            iconID = 22  # fast bedeckt und bedeckt

    # add rain, if necessary
    if iconID == 23 and weatherReportHourly['rain'] > 0.0:
        if weatherReportHourly['rain'] < 0.5:
            iconID = 33  # Leichter Regen
        elif weatherReportHourly['rain'] <= 4:
            iconID = 23  # Regen
        else:
            iconID = 25  # Starker Regen
    return iconID


# Loxone is using www.meteoblue.com for their weather data, it's the same format!
def generateCSV(weatherReport, asl):
    csv = ""
    csv += "<mb_metadata>\n"
    csv += "id;name;longitude;latitude;height (m.asl.);country;timezone;utc-timedifference;sunrise;sunset;\n"
    csv += "local date;weekday;local time;temperature(C);feeledTemperature(C);windspeed(km/h);winddirection(degr);wind gust(km/h);low clouds(%);medium clouds(%);high clouds(%);precipitation(mm);probability of Precip(%);snowFraction;sea level pressure(hPa);relative humidity(%);CAPE;picto-code;radiation (W/m2);\n"
    csv += "</mb_metadata><valid_until>{:{dfmt}}</valid_until>\n".format(
        licenseExpiryDate, dfmt='%Y-%m-%d')
    # CAPE = Convective available potential energy <https://en.wikipedia.org/wiki/Convective_available_potential_energy>
    csv += "<station>\n"
    longitude = weatherReport['lon']
    if longitude < 0:
        longitude = -longitude
        eastwest = 'W'
    else:
        eastwest = 'E'
    latitude = weatherReport['lat']
    if latitude < 0:
        latitude = -latitude
        northsouth = 'S'
    else:
        northsouth = 'N'

    local_tz = pytz.timezone(weatherReport['timezone'])
    utcTimeDiff = local_tz.utcoffset(datetime.datetime.now()).seconds / 3600
    print utcTimeDiff

    sunriseTime = '{:{sunrise}}'.format(datetime.datetime.fromtimestamp(
        weatherReport['daily'][0]['sunrise']), sunrise='%H:%M')
    sunsetTime = '{:{sunset}}'.format(datetime.datetime.fromtimestamp(
        weatherReport['daily'][0]['sunset']), sunset='%H:%M')
    csv += ";Kollerschlag;{lon:.2f}°{eastwest};{lat:.2f}°{northsouth} ;{asl};;CEST;UTC{utcTimedifference:+.1f};{sunrise};{sunset};\n".format(
        lon=longitude, eastwest=eastwest, lat=latitude, northsouth=northsouth, asl=asl, utcTimedifference=utcTimeDiff, sunrise=sunriseTime, sunset=sunsetTime)
    for hourly in weatherReport['hourly']:
        time = datetime.datetime.fromtimestamp(hourly['dt'])
        iconID = loxoneWeatherIcon(hourly)
        csv += '{:{localDate};{weekday};{localTime}};'.format(
            time, localDate='%d.%m.%Y', weekday='%a', localTime='%H')
        csv += '{:5.1f};'.format(hourly['temp'])
        csv += '{:5.1f};'.format(hourly['feels_like'])
        csv += '{:3.0f};'.format(hourly['wind_speed'])
        csv += '{:3.0f};'.format(hourly['wind_deg'])
        if "wind_gust" in hourly:
            csv += '{:3.0f};'.format(hourly['wind_gust'])
        else:
            csv += '{:3.0f};'.format(0)

        csv += '{:3.0f};'.format(0.0)
        csv += '{:3.0f};'.format(hourly['clouds'])
        csv += '{:3.0f};'.format(0.0)
        if "rain" in hourly:
            csv += '{:5.1f};'.format(hourly['rain']["1h"])
        else:
            csv += '{:5.1f};'.format(0.0)
        csv += '{:3.0f};'.format(0.0)
        csv += '{:3.1f};'.format(0.0)
        csv += '{:4.0f};'.format(hourly['pressure'])
        csv += '{:3.0f};'.format(hourly['humidity'])
        csv += '{:6d};'.format(0)
        csv += '{:d};'.format(iconID)
        if "uvi" in hourly:
            csv += '{:4.0f};'.format(hourly['uvi'])
        else:
            csv += '{:4.0f};'.format(0.0)
        csv += '\n'
    csv += "</station>\n"
    return csv


def generateXML(weatherReport, asl):
    xml = '<?xml version="1.0"?>'
    xml += '<metdata_feature_collection p="m" valid_until="{:{dfmt}}">'.format(
        licenseExpiryDate, dfmt='%Y-%m-%d')

    for hourly in weatherReport['hourly']:
        time = datetime.datetime.fromtimestamp(hourly['dt'])
        iconID = loxoneWeatherIcon(hourly)
        xml += '<metdata>'
        xml += '<timepoint>{:%Y-%m-%dT%H:%M:%S}</timepoint>'.format(time)
        xml += '<TT>{:.1f}</TT>'.format(hourly['temp'])  # Temperature (C)
        # Wind Speed (m/s)
        xml += '<FF>{:.1f}</FF>'.format(hourly['wind_speed']*1000/3600)
        windBearing = hourly['wind_deg']-180
        if windBearing < 0:
            windBearing += 360
        xml += '<DD>{:.0f}</DD>'.format(windBearing)  # Wind Speed (Direction)
        if "rain" in hourly:
            # Rainfall (mm)
            xml += '<RR1H>{:5.1f}</RR1H>'.format(hourly['rain']["1h"])
        else:
            xml += '<RR1H>0</RR1H>'

        xml += '<PP0>{:.0f}</PP0>'.format(hourly['pressure'])  # Pressure (hPa)
        xml += '<RH>{:.0f}</RH>'.format(hourly['humidity'])  # Humidity (%)
        # Perceived Temperature (C)
        xml += '<HI>{:.1f}</HI>'.format(hourly['feels_like'])
        # Solar Irradiation (0-20% (<60), 20-40% (<100), 40-100%)
        if "uvi" in hourly:
            xml += '<RAD>{:4.0f}</RAD>'.format(hourly['uvi'])
            xml += '<RAD4C>{:.0f}</RAD4C>'.format(hourly['uvi'])  # UV Index
        else:
            xml += '<RAD>0.0</RAD>'
            xml += '<RAD4C>0.0</RAD4C>'
        xml += '<WW>2</WW>'  # Icon
        # Wind Speed (m/s)
        if "wind_gust" in hourly:
            xml += '<FFX>{:.1f}</FFX>'.format(hourly['wind_gust']*1000/3600)
        xml += '<LC>{:.0f}</LC>'.format(0)  # low clouds
        xml += '<MC>{:.0f}</MC>'.format(hourly['clouds'])  # medium clouds
        xml += '<HC>{:.0f}</HC>'.format(0)  # high clouds

        xml += '</metdata>'
    xml += '</metdata_feature_collection>\n'
    return xml


class Proxy(SimpleHTTPServer.SimpleHTTPRequestHandler):
    def do_GET(self):
        try:
            path, query = self.path.split('?')
        except ValueError:
            self.send_response(404)
            self.end_headers()
            return

        query = urlparse.parse_qs(query)
        self.server_version = 'Apache/2.4.7 (Ubuntu)'
        self.sys_version = ''
        self.protocol_version = 'HTTP/1.1'
        if path != '/forecast/':
            # print(path)
            # print(urlparse.parse_qs(query))
            self.send_response(404)
            self.end_headers()

        self.send_response(200)
        self.send_header('Vary', 'Accept-Encoding')
        self.send_header('Connection', 'close')
        self.send_header('Transfer-Encoding', 'chunked')
        if 'asl' in query:
            asl = int(query['asl'][0])
        else:
            asl = 0
        lat, long = query['coord'][0].split(',')
        if os.path.isfile('weather.json'):
            jsonReport = json.loads(open('weather.json').read())
        else:
            jsonReport = json.loads(
                downloadReport(float(long), float(lat), asl))
        if 'format' in query and int(query['format'][0]) == 1:
            reply = generateCSV(jsonReport, asl)
            self.send_header('Content-Type', 'text/plain')
        else:
            reply = generateXML(jsonReport, asl)
            self.send_header('Content-Type', 'text/xml')
        self.end_headers()
        self.wfile.write("%x\r\n%s\r\n" % (len(reply), reply))
        self.wfile.write("0\r\n\r\n")


SocketServer.TCPServer.allow_reuse_address = True
httpd = SocketServer.ForkingTCPServer(('', LOXONE_WEATHER_SERVICE_PORT), Proxy)
httpd.serve_forever()
