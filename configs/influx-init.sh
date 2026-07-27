#!/bin/bash
set -e

influx bucket create -n mag_sensor -o ${DOCKER_INFLUXDB_INIT_ORG} -t ${DOCKER_INFLUXDB_INIT_ADMIN_TOKEN} -r 24h
