#include "Python.h"
#include <AudioToolbox/AudioServices.h>

#define FourCC2Str(code) (char[5]){(code >> 24) & 0xFF, (code >> 16) & 0xFF, (code >> 8) & 0xFF, code & 0xFF, 0}

static PyObject *
OSError_from_HALError(const char *failed_operation, OSStatus err) {
    // these error codes are actually mnemonic, so display them
    return PyErr_Format(PyExc_OSError,
                        "%s failed (%ld - %s)",
                        failed_operation, (long)err, FourCC2Str(err));
}

static PyObject *
AudioDevice_default_output_device_is_airplay(PyObject *self, PyObject *args) {
  AudioObjectPropertyAddress propertyAddress;
  propertyAddress.mScope = kAudioObjectPropertyScopeGlobal;
  propertyAddress.mElement = kAudioObjectPropertyElementMaster;
  propertyAddress.mSelector = kAudioHardwarePropertyDefaultOutputDevice;

  AudioDeviceID	deviceID = kAudioDeviceUnknown;
  UInt32 size = sizeof(deviceID);
  OSStatus err;
  
  err = AudioObjectGetPropertyData(kAudioObjectSystemObject,
                                   &propertyAddress, 0, NULL,
                                   &size, &deviceID);
  if (err != noErr)
    return OSError_from_HALError("AudioObjectGetPropertyData", err);
  
  if (deviceID == kAudioDeviceUnknown)
    Py_RETURN_NONE;

  UInt32 transportType;
  propertyAddress.mSelector = kAudioDevicePropertyTransportType,
  err = AudioObjectGetPropertyData(deviceID,
                                   &propertyAddress, 0, NULL,
                                   &size, &transportType);
  if (err == kAudioHardwareBadObjectError)
    Py_RETURN_NONE;
  if (err != noErr)
    return OSError_from_HALError("AudioObjectGetPropertyData", err);

  if (transportType == kAudioDeviceTransportTypeAirPlay)
    Py_RETURN_TRUE;
  else
    Py_RETURN_FALSE;
}

static PyObject *default_output_device_changed_callback = NULL;

OSStatus 
output_device_changed_listener(AudioObjectID inObjectID,
                               UInt32 inNumberAddresses,
                               const AudioObjectPropertyAddress inAddresses[],
                               void *inClientData) {
  PyGILState_STATE gstate = PyGILState_Ensure();
  PyObject_CallObject(default_output_device_changed_callback, NULL);
  PyGILState_Release(gstate);

  return noErr;
}

static PyObject *
AudioDevice_set_default_output_device_changed_callback(PyObject *self,
                                                       PyObject *args) {
  PyObject *new_callback;
  if (!PyArg_ParseTuple(args, "O", &new_callback))
    return NULL;

  if (!PyCallable_Check(new_callback)) {
    PyErr_SetString(PyExc_TypeError, "parameter must be callable");
    return NULL;
  }
  Py_INCREF(new_callback);
  if (default_output_device_changed_callback == NULL) {
    AudioObjectPropertyAddress propertyAddress;
    propertyAddress.mScope = kAudioObjectPropertyScopeGlobal;
    propertyAddress.mElement = kAudioObjectPropertyElementMaster;
    propertyAddress.mSelector = kAudioHardwarePropertyDefaultOutputDevice;

    OSStatus err;
    err = AudioObjectAddPropertyListener(kAudioObjectSystemObject,
                                         &propertyAddress,
                                         &output_device_changed_listener,
                                         NULL);
    if (err != noErr)
      return OSError_from_HALError("AudioObjectAddPropertyListener", err);
  } else {
    Py_DECREF(default_output_device_changed_callback);
  }
  default_output_device_changed_callback = new_callback;
  
  Py_RETURN_NONE;
}

static PyMethodDef AudioDevicemodule_methods[] = {
  {"default_output_device_is_airplay",
   AudioDevice_default_output_device_is_airplay, METH_NOARGS,
   "default_output_device() -> bool or None\n\n"
   "Return whether the default CoreAudio output device is an AirPlay device."},
  {"set_default_output_device_changed_callback",
   AudioDevice_set_default_output_device_changed_callback, METH_VARARGS,
   "set_default_output_device_changed_callback(callable)\n\n"
   "Set a callback invoked when the default CoreAudio output device changes."},
  {NULL, NULL, 0, NULL}
};

PyMODINIT_FUNC
initAudioDevice(void) {
  (void)Py_InitModule("AudioDevice", AudioDevicemodule_methods);
}
