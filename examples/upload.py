#https://docs.openstack.org/python-swiftclient/latest/service-api.html
#Modified by Jialin Liu
#Date Oct 5 2017
# This script can test the write performance on lustre and openstack-swift
# It first generates a HDF5 file in memory with a 2D float dataset, 
# then writes that directly to targeted storage

import tables,io,os
import logging
from sys import argv
import time
import h5py
import numpy as np
from swiftclient.multithreading import OutputManager
from swiftclient.service import SwiftError, SwiftService, SwiftUploadObject
logging.basicConfig(level=logging.ERROR)
logging.getLogger("requests").setLevel(logging.CRITICAL)
logging.getLogger("swiftclient").setLevel(logging.CRITICAL)
logger = logging.getLogger(__name__)

def swift_file_commit(_opts, container, obj_name, obj_source=None):
 with SwiftService(options=_opts) as swift, OutputManager() as out_manager:
    try:
        if obj_source is None:
           obj_source=obj_name # file path
           #check if file exists
           if(not os.path.exists(obj_source)):
             print ('File %s does not exist'%obj_source)
             exit()
        objs = [ SwiftUploadObject(obj_source,obj_name)]  # (source, object name) --> (value,key)
        for r in swift.upload(container, objs):
         if r['success']:
            if 'object' in r:
                print(r['object'])
            elif 'for_object' in r:
                print(
                    '%s segment %s' % (r['for_object'],
                                       r['segment_index'])
                    )
         else:
            error = r['error']
            if r['action'] == "create_container":
                logger.warning(
                    'Warning: failed to create container '
                    "'%s'%s", container, error
                )
            elif r['action'] == "upload_object":
                logger.error(
                    "Failed to upload object %s to container %s: %s" %
                    (container, r['object'], error)
                )
            else:
                logger.error("%s" % error)

    except SwiftError as e:
        logger.error(e.value)


def test_write_swift(_opts,path,fname,dname,dimx,dimy):
 try:
  fx = tables.open_file(h5fname,'a',driver='H5FD_CORE',driver_core_backing_store=0)
 except Exception as e:
  print ('creating file in test swift fails')
  exit()
 # Do an implicit swift.upload for this empty file
 # swift_file_commit(container,h5fname)
 # Fill in the file with real data
 # [future] do an implicit swift.download
 # for now, just read it locally
 try:
  arr = np.ndarray(shape=(dimx,dimy),dtype=float)
  arr.fill(3.1415926)
  # write will implicitly happens by default, we want to bypass this, and directly talk with swift
 except Exception as e:
  print ('creating dataset in swift test fails')
  exit()

 start = time.time()
 #get image of hdf5 file
 try:
  dset=fx.create_array(fx.root,dname,arr)
  image = fx.get_file_image()
 except Exception as e:
  print ('geting h5 file image fails')
  exit()
 #convert image to file-like object
 try:
  fobj = io.BytesIO(image)
 except Exception as e:
  print ('geting file-like object fails')
  exit()
 start2 = time.time()
 swift_file_commit(_opts, container, h5fname, fobj)
 end = time.time()

 print('[Swift] Writing cost %.2f second'%(end-start))
 print('[Swift] 1. File image/array creating cost %.2f second'%(start2-start))
 print('[Swift] 2. Uploading cost %.2f second'%(end-start2))
 try:
  fx.close()
 except Exception as e:
  print ('file closing fails in swift test')
  exit()

def test_write_lustre(path,fname,dname,dimx,dimy):
  if path=='scratch':
   fdir=os.environ['SCRATCH']
   ftestdir=fdir+'/swift-lustre-test/'
   try:
     os.mkdirs(ftestdir)
   except:
     pass
   fname=ftestdir+fname
  if os.path.exists(fname):
   print ("%s exists in lustre write test\n"%fname)
   exit()
  arr = np.ndarray(shape=(dimx,dimy),dtype=float)
  arr.fill(3.1415926)
  start =  time.time()
  try:
    f=h5py.File(fname,'a',driver='core')
    dset=f.create_dataset(dname,(dimx,dimy),data=arr) # no write with core driver
    f.close() # writes happens, but probably in page buffer
  except Exception as e:
   print ('lustre write fails in file write')
   print (e)
   exit()
  end = time.time()
  print('[Lustre] Writing cost %.2f second'%(end-start))
if __name__=='__main__':
   _opts = {'object_uu_threads': 10, 'segment_size': 1048576}
   if(len(argv)<6):
     print ("Parameters: container/path name, filename, dname, dimx, dimy")
     exit()
   h5fname = argv[2]
   container = argv[1]
   dimx=int(argv[4])
   dimy=int(argv[5])
   dname=argv[3] 
   
   test_write_swift(_opts,container,h5fname,dname,dimx,dimy)
   test_write_lustre(container,h5fname,dname,dimx,dimy)


