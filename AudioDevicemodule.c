#include "Python.h"
#include <AudioToolbox/AudioServices.h>

static PyObject
*AudioDevice_default_output_device_is_airplay(PyObject *self, PyObject *args) {
  AudioObjectPropertyAddress propertyAddress;
  propertyAddress.mScope = kAudioObjectPropertyScopeGlobal;
  propertyAddress.mElement = kAudioObjectPropertyElementMaster;
  propertyAddress.mSelector = kAudioHardwarePropertyDefaultOutputDevice;

  AudioDeviceID	deviceID = kAudioDeviceUnknown;
  UInt32 size = sizeof(deviceID);
  OSStatus err;
  
  err = AudioHardwareServiceGetPropertyData(kAudioObjectSystemObject,
                                            &propertyAddress, 0, NULL,
                                            &size, &deviceID);
  if (err != noErr)
    return PyErr_Format(PyExc_OSError,
                        "AudioHardwareServiceGetPropertyData failed (%ld)",
                        (long)err);
  
  if (deviceID == kAudioDeviceUnknown)
    Py_RETURN_NONE;

  UInt32 transportType;
  propertyAddress.mSelector = kAudioDevicePropertyTransportType,
  err = AudioObjectGetPropertyData(deviceID,
                                   &propertyAddress, 0, NULL,
                                   &size, &transportType);
  if (err != noErr)
    return PyErr_Format(PyExc_OSError,
                        "AudioObjectGetPropertyData failed (%ld)",
                        (long)err);

  if (transportType == kAudioDeviceTransportTypeAirPlay)
      Py_RETURN_TRUE;
  else
      Py_RETURN_FALSE;
}

// XXX device changed notifications:
// http://stackoverflow.com/questions/9674666/

static PyMethodDef AudioDevicemodule_methods[] = {
  {"default_output_device_is_airplay",
   AudioDevice_default_output_device_is_airplay, METH_NOARGS,
   "default_output_device() -> bool or None\n\n"
   "Return whether the default CoreAudio output device is an AirPlay device."},
  {NULL, NULL, 0, NULL}
};

PyMODINIT_FUNC
initAudioDevice(void) {
  (void)Py_InitModule("AudioDevice", AudioDevicemodule_methods);
}
