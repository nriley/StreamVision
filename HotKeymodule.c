#include "Python.h"
#include "pymactoolbox.h"

#include <Carbon/Carbon.h>

/* from _CarbonEvtmodule.c */
extern PyTypeObject EventHotKeyRef_Type;
#define EventHotKeyRef_Check(x) ((x)->ob_type == &EventHotKeyRef_Type || PyObject_TypeCheck((x), &EventHotKeyRef_Type))
typedef struct EventHotKeyRefObject {
  PyObject_HEAD
  EventHotKeyRef ob_itself;
} EventHotKeyRefObject;

static PyObject
*HotKey_HotKeyAddress(PyObject *self, PyObject *args) {
  PyObject *v;
  if (!PyArg_ParseTuple(args, "O", &v))
    return NULL;
  if (!EventHotKeyRef_Check(v)) {
    PyErr_SetString(PyExc_TypeError, "_CarbonEvt.EventHotKeyRef required");
    return NULL;
  }
  return PyInt_FromLong((int)((EventHotKeyRefObject *)v)->ob_itself);
}

static PyMethodDef HotKeymodule_methods[] = {
  {"HotKeyAddress", HotKey_HotKeyAddress, METH_VARARGS,
   "HotKeyAddress(_CarbonEvt.EventHotKeyRef) -> integer\n\n"
   "Return the address of the underlying EventHotKeyRef (passed as data1 in hot key NSEvents)."},
  {NULL, NULL, 0, NULL}
};

PyMODINIT_FUNC
initHotKey(void) {
  (void)Py_InitModule("HotKey", HotKeymodule_methods);
}
