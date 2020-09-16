import axios from "axios";

export class TraccarDevice {
    constructor(id, name, status, lastUpdate, category) {
        this.id = id;
        this.name = name;
        this.status = status;
        this.lastUpdate = lastUpdate;
        this.category = category;
        this.devices = [];
    }
}

export class TraccarDeviceList {
    constructor(devices) {
        this.devices = devices
    }

    deviceById(id) {
        return this.devices.find(device => device.id === id);
    }

    deviceByName(name) {
        return this.devices.find(device => device.name === name);
    }


}