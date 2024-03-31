# -*- coding: utf-8 -*-
# !/usr/bin/python3

import copy
import datetime
import json
import logging
import os
import socket
import traceback

import requests
import urllib3
from Misc import sendEmail, get911

urllib3.disable_warnings()


def getJSONInfo(JSONInfo):
    """
    Extracts information from a JSON dictionary based on specified metrics.

    Args:
        JSONInfo (dict): The JSON dictionary containing the information.

    Returns:
        dict: A dictionary containing extracted information based on the specified metrics.
    """
    JSONInfo_ = {"Date": datetime.datetime.now().strftime("%Y/%m/%d %H:%M")}

    for metric_name, metric_subs in METRICS.items():
        if JSONInfo[metric_name].get("hasInfo") == "None":
            continue

        JSONInfo_[metric_name] = {}
        for sub_metric in metric_subs:
            if isinstance(sub_metric, str):
                JSONInfo_[metric_name][sub_metric] = JSONInfo[metric_name][sub_metric]
            elif isinstance(sub_metric, dict):
                for sub_metric_name, sub_metric_values in sub_metric.items():
                    if JSONInfo[metric_name][sub_metric_name].get("hasInfo") == "None":
                        continue
                    for value in sub_metric_values:
                        JSONInfo_[metric_name][sub_metric_name + "_" + value] = JSONInfo[metric_name][sub_metric_name][value]

    return JSONInfo_


def checkAlarms(JSONInfo):
    """
    Check for system alarms based on temperature and environmental conditions.

    Parameters:
    - JSONInfo (dict): A dictionary containing system information, including CPU temperature and ambient data.

    Returns:
    None
    """

    # Check CPU Usage
    cpu_usage = JSONInfo["CPU"]["Percentage"]
    if cpu_usage >= MAX_CPU_USAGE:
        logger.warning("HIGH CPU USAGE")
        logger.warning(f"CPU Usage: {cpu_usage} %")
        sendEmail("HIGH CPU USAGE", f"CPU Usage: {cpu_usage} %")

    # Check Temperature
    temperature = JSONInfo["CPU"]["Temperature"]
    if temperature >= MAX_CPU_TEMP_C:
        logger.warning("OVERHEAT")
        logger.warning(f"CPU Temperature: {temperature} ºC")
        sendEmail("OVERHEAT", f"CPU Temperature: {temperature} ºC")

    # Check RAM Usage
    ram_usage = JSONInfo["Memory"]["Percentage"]
    if ram_usage >= MAX_RAM_USAGE:
        logger.warning("HIGH CPU USAGE")
        logger.warning(f"RAM Usage: {ram_usage} %")
        sendEmail("HIGH RAM USAGE", f"RAM Usage: {ram_usage} %")

    # Check Disk Usage
    sdcard_usage = JSONInfo["Disks"]["SDCard_Percentage"]
    if sdcard_usage >= MAX_SDCARD_USAGE:
        logger.warning("HIGH SDCARD USAGE")
        logger.warning(f"Sdcard Usage: {sdcard_usage} %")
        sendEmail("HIGH SDCARD USAGE", f"Sdcard Usage: {sdcard_usage} %")

    # Check Ambient
    if "Ambient" in JSONInfo.keys():
        temp_c = JSONInfo["Ambient"]["TemperatureC"]
        humidity = JSONInfo["Ambient"]["Humidity"]
        pressure = "Not Available" if "Pressure" not in JSONInfo["Ambient"].keys() else JSONInfo["Ambient"]["Pressure"]

        subject = "AMBIENT WARNING"
        body = []
        if temp_c <= TEMP_C_RANGE[0]:
            msg = f"ICE - Ambient Temperature ({temp_c} ºC) bellow threshold ({TEMP_C_RANGE[0]} ºC)"
            logger.warning(msg)
            body.append(msg)
        if temp_c >= TEMP_C_RANGE[1]:
            msg = f"FIRE - Ambient Temperature ({temp_c} ºC) above threshold ({TEMP_C_RANGE[1]} ºC)"
            logger.warning(msg)
            body.append(msg)

        if humidity <= HUMIDITY_RANGE[0]:
            msg = f"DRY - Ambient Humidity ({humidity} %) bellow threshold ({HUMIDITY_RANGE[0]} %)"
            logger.warning(msg)
            body.append(msg)
        if humidity >= HUMIDITY_RANGE[1]:
            msg = f"FLOOD - Ambient Humidity ({humidity} %) above threshold ({HUMIDITY_RANGE[1]} %)"
            logger.warning(msg)
            body.append(msg)

        if pressure != "Not Available":
            if pressure <= PRESSURE_RANGE[0]:
                msg = f"LOW Pressure - ({pressure} hPa) bellow threshold ({PRESSURE_RANGE[0]} hPa)"
                logger.warning(msg)
                body.append(msg)
            if pressure >= PRESSURE_RANGE[1]:
                msg = f"HIGH Pressure ({pressure} hPa) above threshold ({PRESSURE_RANGE[1]} hPa)"
                logger.warning(msg)
                body.append(msg)

        if len(body) != 0:
            sendEmail(subject, body)

    return


def generate_expected_structure(data):
    """
    Generate the expected structure of nested dictionaries based on the provided data.

    Parameters:
    - data (list): A list of dictionaries representing the input data.

    Returns:
    dict: The expected structure of nested dictionaries.
    """
    # Initialize an empty dictionary for the expected structure
    expected_structure = {}

    # Iterate through the input data and build the structure
    for item in data:
        for key, value in item.items():
            if isinstance(value, dict):
                # Recursively generate the structure for nested dictionaries
                expected_structure[key] = generate_expected_structure([value])
            else:
                # Use the type of the value as the default
                expected_structure[key] = type(value)()

    return expected_structure


def fill_missing_keys(data):
    """
    Fill missing keys in a list of dictionaries with default values based on the expected structure.

    Parameters:
    - data (list): A list of dictionaries representing the input data.

    Returns:
    list: The input data with missing keys filled in with default values.
    """
    # Generate the expected structure based on the first dictionary in the data
    expected_structure = generate_expected_structure(data)

    # Iterate through the input data
    for item in data:
        # Recursively fill missing keys based on the expected structure
        fill_missing_keys_recursive(item, expected_structure)

    return data


def fill_missing_keys_recursive(data, expected_structure):
    """
    Recursively fill missing keys in a dictionary with default values based on the expected structure.

    Parameters:
    - data (dict): A dictionary representing the input data.
    - expected_structure (dict): The expected structure of nested dictionaries.

    Returns:
    None
    """
    for key, value in expected_structure.items():
        if key not in data:
            data[key] = value
        elif isinstance(data[key], dict) and isinstance(value, dict):
            # Recursively fill missing keys for nested dictionaries
            fill_missing_keys_recursive(data[key], value)


def main():
    # Get hostname
    hostname = str(socket.gethostname()).upper()
    global METRICS, METRICS_BAK, SAVED_INFO

    # Get Hardware Info JSON
    logger.info("Get Hardware Info JSON")
    response = requests.get(f"https://monitor.{hostname}.xhico/stats/getHWInfo", auth=(get911("APACHE_USER"), get911("APACHE_PASS")))
    if response.status_code != 200:
        logger.error(f"Failed to get hardware info JSON. Status code: {response.status_code}")
        return
    JSONInfo = response.json()

    # Parse JSONInfo
    logger.info("Parse JSONInfo")
    JSONInfo = getJSONInfo(JSONInfo)

    # Check for alarms
    logger.info("Check for alarms")
    checkAlarms(JSONInfo)

    # Set Historic Data
    logger.info("Set Historic Data")
    SAVED_INFO = list(reversed(SAVED_INFO))
    SAVED_INFO.append(JSONInfo)
    SAVED_INFO = fill_missing_keys(SAVED_INFO)
    savedInfo = list(reversed(SAVED_INFO))
    with open(savedInfoFile, "w") as outFile:
        json.dump(savedInfo, outFile, indent=2)


if __name__ == '__main__':
    # Define constants
    LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.path.abspath(__file__).replace(".py", ".log"))

    # Set logging configuration
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()])
    logger = logging.getLogger()

    # Log the start of the script
    logger.info("----------------------------------------------------")

    # Load configuration from JSON file
    configFile = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
    with open(configFile) as inFile:
        config = json.load(inFile)
    MAX_CPU_TEMP_C = config["MAX_CPU_TEMP_C"]
    MAX_CPU_USAGE = config["MAX_CPU_USAGE"]
    MAX_RAM_USAGE = config["MAX_RAM_USAGE"]
    MAX_SDCARD_USAGE = config["MAX_SDCARD_USAGE"]
    TEMP_C_RANGE = config["TEMP_C_RANGE"]
    HUMIDITY_RANGE = config["HUMIDITY_RANGE"]
    PRESSURE_RANGE = config["PRESSURE_RANGE"]
    METRICS = config["METRICS"]
    METRICS_BAK = copy.deepcopy(config["METRICS"])

    # Load SAVED_INFO from JSON file
    savedInfoFile = os.path.join(os.path.dirname(os.path.abspath(__file__)), "saved_info.json")
    if not os.path.exists(savedInfoFile):
        with open(savedInfoFile, "w") as outFile:
            json.dump([], outFile, indent=2)
    with open(savedInfoFile) as inFile:
        SAVED_INFO = json.load(inFile)

    try:
        # Call the main function
        main()
    except Exception as ex:
        # Log the error and send an email notification
        logger.error(traceback.format_exc())
        sendEmail(os.path.basename(__file__), str(traceback.format_exc()))
    finally:
        # Log the end of the script
        logger.info("End")
