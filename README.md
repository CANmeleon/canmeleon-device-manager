# CANmeleon Device Manager — USB-CAN/CAN FD Firmware Management

[English](README.md) · [简体中文](README.zh-CN.md)

CANmeleon Device Manager is a Windows tool for connecting supported USB-CAN/CAN FD devices, viewing device information, and installing, updating or switching CANmeleon firmware. Browse the firmware catalog, inspect installed firmware and storage, and recover supported devices from KH-Updater mode.

**[Download for Windows x64](https://canmeleon.com/en/device-manager/#downloads)** · [Supported hardware](https://canmeleon.com/en/firmware/devices/) · [Firmware catalog](https://github.com/CANmeleon/canmeleon-usb-can-firmware) · [User guide](https://canmeleon.com/en/device-manager/)

## Download and install

| Package | Install |
| --- | --- |
| [Windows x64 installer](https://gitee.com/ChengDu-KunHong/canmeleon-device-manager/releases/download/latest/CANmeleon-device-manager-setup-x64.exe) | Run the installer and follow the setup wizard. |
| [Windows x64 portable ZIP](https://gitee.com/ChengDu-KunHong/canmeleon-device-manager/releases/download/latest/CANmeleon-device-manager-win64.zip) | Extract the complete archive and run `CANmeleon-device-manager.exe`. |

[Software release notes](https://gitee.com/ChengDu-KunHong/canmeleon-device-manager/releases). The linked packages are hosted on Gitee. The illustrated user guide covers version **0.8.5**; device-manager versions and firmware-package versions are separate.

## What you can do

| Task | Function |
| --- | --- |
| Identify a device | Inspect the USB node, driver, device information and installed firmware. |
| Choose firmware | Browse the catalog and check applicability after connecting a supported device. |
| Manage storage | Review installed firmware, available space and pending changes before writing. |
| Install and update | Download a release or import a complete offline firmware ZIP, then install suitable firmware. |
| Switch firmware | Select an installed firmware image; the device reconnects with its corresponding USB identity and driver. |
| Recover a device | Restore suitable firmware to a supported device in KH-Updater recovery mode. |

Multiple firmware images can be stored where hardware, storage and licensing permit. One firmware runs at a time. Channel counts, available modes and software-controlled termination depend on the device and firmware.

## Connect and install your first firmware

1. Check the exact model in the [supported device list](https://canmeleon.com/en/firmware/devices/) and install the driver required by its active firmware.
2. Close other CAN software using the device, connect it by USB, and select **Refresh** in the manager.
3. Select the device and click **Connect**. Review its information and installed firmware.
4. Choose a release in **Firmware Catalog** and select applicable firmware. Review the required space and pending changes.
5. Confirm **Install on device** or **Update now** and wait for writing to finish. Keep the device connected and the manager open during writing.
6. Reconnect and verify the installed version. Use **Switch to this firmware** to run the selected image, then open the corresponding CAN software after USB re-enumeration.

See the [firmware management guide](https://canmeleon.com/en/device-manager/firmware-management/) for the complete workflow.

## Offline updates and recovery

Use **Import firmware ZIP** with a complete release from the [firmware download guide](https://github.com/CANmeleon/canmeleon-usb-can-firmware#download-and-install). Importing prepares the PC cache; installation is a separate step.

For a device shown as **Recovery mode**, follow [device recovery](https://canmeleon.com/en/device-manager/updates-and-recovery/#device-recovery). Recovery can overwrite installed firmware. Verify the target device and package, and keep power connected until writing completes.

## Frequently asked questions

**Can the manager install firmware on any USB-CAN adapter?**

Use hardware listed for CANmeleon management. A detected USB name or a visible catalog entry alone does not establish installation support. Check the connected device's applicability result.

**Does switching firmware also start CANoe, PCAN-View or another CAN tool?**

Switching changes the firmware running on the device. Open the PC software separately and use the driver required by that firmware.

**Why did downloading a firmware release not change my device version?**

Downloading or importing updates the PC cache. Prepare and apply an installation plan, then reconnect to read the device version.

**Where is the source code?**

This repository provides documentation and links to distributed software packages. Refer to the relevant package for its licensing information.

## Help and feedback

- [Troubleshooting](https://canmeleon.com/en/device-manager/faq/) for device detection, drivers, storage and update errors.
- [Report a manager issue](https://github.com/CANmeleon/canmeleon-device-manager/issues) with the device model, manager and firmware versions, exact error and steps to reproduce. Existing technical support: [support@kunhong-elec.com](mailto:support@kunhong-elec.com).
- [Firmware issues](https://github.com/CANmeleon/canmeleon-usb-can-firmware/issues) · [VN16xx firmware guide](https://github.com/CANmeleon/canmeleon-VN16xx-firmware).
