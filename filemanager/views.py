#coding: utf-8
from __future__ import absolute_import

import mimetypes

from django.contrib import auth
from django.http import Http404
from django.conf import settings as global_settings
from django.shortcuts import get_object_or_404, render_to_response, redirect
from django.http import HttpResponseRedirect, HttpResponse, Http404
from django.dispatch.dispatcher import Signal
from django.core.urlresolvers import reverse
from django.views.decorators.csrf import csrf_exempt

from .models import FileCategory, StaticFile
from .forms import StaticFileForm
from .img import ThumbnailBackend
from .settings import AVAILABLE_SIZES

from . import settings
from seautils.views.decorators import expire_in

from seautils.views.decorators import render_with
from django.template.context import RequestContext
from django.utils.functional import SimpleLazyObject
from django.contrib.auth.models import User
from filemanager.fields import ImageField
from filemanager.models import generate_file_path
from django.db.models.fields.files import FileField
from os.path import basename
from django.utils import simplejson as json
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image


file_uploaded = Signal(providing_args=["signal_key", "static_file_instance"])

def upload_file(request, signal_key):
    if not request.method == 'POST':
        raise Http404
    files = {}
    files['static_file'] = request.FILES['file']
    form_data = {'author': request.user,
            'category': FileCategory.objects.get_or_create(
                name=global_settings.CAREGIVERS_FILE_CATEGORY_NAME)[0],
            'filename': files['static_file'].name,
            'description': ' ' }
    form = StaticFileForm(form_data, files)
    if form.is_valid():
        static_file = form.save(commit=False)
        [setattr(static_file, k, v) for k, v in form_data.items()]
        static_file.save()
        file_uploaded.send(None, static_file_instance=static_file, signal_key=signal_key)
        if request.is_ajax():
            response = HttpResponse('{"jsonrpc" : "2.0", "result" : null, "id" : "id"}',
                    mimetype='text/plain; charset=UTF-8')
            return response
        else:
            return HttpResponseRedirect(reverse('plupload_sample.upload.views.upload_file'))

@expire_in(seconds=settings.THUMBNAIL_EXPIRES)
def serve_img(request, file_id, params, ext):
    """
    Params:
    size_index
    crop_param
    """
    params_list = params.split(',')
    try:
        size_index = int(params_list[0] if params else -1)
    except ValueError:
        raise Http404('Invalid params')
    try:
        size = AVAILABLE_SIZES[size_index - 1]
    except IndexError:
        raise Http404('Invalid size.')
    
    crop_param = None
    crop = {}
    if len(params_list) > 2:
        crop_param = params_list[2]
        
    static_file = get_object_or_404(StaticFile, id=file_id)
    
    if static_file and static_file.crop_coords != "":
        crop_coords = map(int, static_file.crop_coords.split(','))        
        crop = {
                'transformation': 0,
                'cropX': crop_coords[0],
                'cropY': crop_coords[1],
                'cropWidth': crop_coords[2],
                'cropHeight': crop_coords[3],
                }
    # TODO oryginalny rozmiar
    tb = ThumbnailBackend()
    size_str = "%sx%s" % (size[0], size[1]) if size != -1 else ''
    thumb_args = [static_file.static_file, size_str]
    thumb_kwargs = {}
    
    if crop_param:
        thumb_kwargs['crop'] = crop_param
    if crop:
        thumb_kwargs['geometry'] = crop
    else:
        thumb_kwargs['geometry'] = None
    ni = tb.get_thumbnail(*thumb_args, **thumb_kwargs)

    mimetype, encoding = mimetypes.guess_type(static_file.filename)
    mimetype = mimetype or 'application/octet-stream'

    image_format = 'JPEG'
    ext = ext.lower()
    if ext == 'png':
        image_format = 'PNG'
    
    response = HttpResponse()
    ni.save(response, image_format, quality=settings.THUMBNAIL_QUALITY)
    response['Content-Type'] = '%s; charset=utf-8' % (mimetype)
    return response

@csrf_exempt 
def upload_multiple(request):
    if request.method == 'POST':
        callback = request.GET.get( 'callback', None ) 
        categoryNumber =  request.GET['category']
        description = request.GET['description']
        image_author = request.GET['image_author']
        filename = request.GET['qqfile']
        
        file_contents = SimpleUploadedFile(filename, request.raw_post_data)
        img = Image.open(file_contents)

        path = generate_file_path(None, request.GET['qqfile'])

        st = StaticFile()
        st.author = User.objects.get(id=request.user.id)
        st.category = FileCategory.objects.get(id=categoryNumber)
        st.static_file = file_contents
        st.filename = filename
        st.image_author = image_author
        st.description = description
        st.width = img.size[0]
        st.height = img.size[1]
        st.save(force_insert=True)
        path = basename(path).split('.')[0]
        path = "/files/img/%d,%d,%d.%s" % (int(path) + 1, st.type, st.file_version, st.file_ext())  
        return HttpResponse(json.dumps ({"path": path}), mimetype="application/json")
    return redirect(reverse('admin:filemanager_proxymodel_add'))
