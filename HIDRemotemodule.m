#include "Python.h"
#include "HID_Utilities_External.h"
#include <IOKit/hid/IOHIDUsageTables.h>
#import <Cocoa/Cocoa.h>

static hu_device_t *device = NULL;

static void callback(void *target, IOReturn result, void *refcon, void *sender) {
  IOHIDEventStruct event;
  while (HIDGetEvent(device, &event)) {
    if (event.type != kIOHIDElementTypeInput_Button ||
        event.elementCookie != (void *)4) continue;
	Nanoseconds nanoTimestamp = AbsoluteToNanoseconds(event.timestamp);
    UInt64 realTimestamp = UnsignedWideToUInt64(nanoTimestamp);
    NSTimeInterval timestamp = ((NSTimeInterval)realTimestamp)/1000000000;
    [NSApp sendEvent: [NSEvent otherEventWithType: NSApplicationDefined
                                         location: NSZeroPoint
                                    modifierFlags: 0
                                        timestamp: timestamp
                                     windowNumber: 0
                                          context: nil
                                          subtype: 0
                                            data1: event.value
                                            data2: 0]];
  }
}

static PyObject
*HIDRemote_connect(PyObject *self, PyObject *args) {
  if (device != NULL) {
    PyErr_SetString(PyExc_OSError, "already connected");
    return NULL;
  }
  if (!HIDBuildDeviceList(kHIDPage_Consumer, kHIDUsage_Csmr_ConsumerControl)) {
    PyErr_SetString(PyExc_OSError, "can't get HID device list");
    return NULL;
  }
  device = HIDGetFirstDevice();
  if (device == NULL) {
    HIDReleaseDeviceList();
	PyErr_SetString(PyExc_OSError, "no HID consumer control devices");
	return NULL;
  }
  if (HIDQueueDevice(device) != kIOReturnSuccess) {
    HIDDequeueDevice(device);
    HIDReleaseDeviceList();
	PyErr_SetString(PyExc_OSError, "can't queue HID consumer control device");
    return NULL;
  }
  if (HIDSetQueueCallback(device, callback, NULL, NULL) != kIOReturnSuccess) {
    HIDDequeueDevice(device);
    HIDReleaseDeviceList();
	PyErr_SetString(PyExc_OSError, "can't register queue callback");
    return NULL;
  }
  Py_INCREF(Py_None);
  return Py_None;
}

static PyObject
*HIDRemote_disconnect(PyObject *self, PyObject *args) {
  if (device == NULL) {
    PyErr_SetString(PyExc_OSError, "not connected");
    return NULL;
  }
  HIDDequeueDevice(device);
  HIDReleaseDeviceList();
  Py_INCREF(Py_None);
  return Py_None;
}

static PyMethodDef HIDRemotemodule_methods[] = {
  {"connect", HIDRemote_connect, METH_NOARGS,
   "connect()\n\n"
   "Connect to the first consumer control USB HID device and begin receiving events."},
  {"disconnect", HIDRemote_disconnect, METH_NOARGS,
   "disconnect()\n\n"
   "Disconnect from the attached consumer control USB HID device and stop receiving events."},
  {NULL, NULL, 0, NULL}
};

PyMODINIT_FUNC
initHIDRemote(void) {
  (void)Py_InitModule("HIDRemote", HIDRemotemodule_methods);
}
