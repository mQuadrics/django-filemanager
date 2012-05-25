#coding: utf-8

from __future__ import absolute_import

from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.conf.urls.defaults import patterns, url
from django.conf import settings
from PIL import Image

from .models import StaticFile, FileCategory, ProxyModel, generate_file_path
from seautils.baseadmin.admin import BaseModelAdmin
from seautils.utils import compile_js
from copy import copy
import urllib
from django.core.files import File

class FileAdmin(BaseModelAdmin):
    class Media:
        js = compile_js(['filemanager/js/admin_list.coffee', 'filemanager/js/addr_gen.coffee'])
        js += ['filemanager/js/jquery.min.js']
    change_form_template = 'filemanager/change_form.html'
    change_list_template = 'filemanager/change_list.html'
    
    date_hierarchy = ('create_time')
    list_display = ('icon', 'static_file', 'category', 'create_time', 'file_ext')
    list_display_links = ('static_file', 'create_time', )
    list_filter = ('create_time','category',)
    search_fields = ('filename', 'description')
    readonly_fields = ( 'width', 'height', 'type',)
    exclude = ('author', 'file_version',)
    ordering = ('-create_time',)
    save_as = True
    
    def icon(self, obj):
        if obj.is_image():
            return """
                <div class="image" style="position: relative; float: left;">
                    <img width="100" src="%s" />
                    <img src="%sadmin_tools/images/icon_image.png" style="position: absolute; right: 2px; bottom: 2px;" alt="Obraz" />
                </div>
            """ % ( obj.icon_path(), settings.STATIC_URL )
        
        elif obj.is_video():
            return """
                <div class="video" style="position: relative; float: left;">
                    <img width="100" src="%s" />
                    <img src="%sadmin_tools/images/icon_movie.png" style="position: absolute; right: 2px; bottom: 2px;" alt="Wideo" />
                </div>
            """ % ( obj.icon_path(), settings.STATIC_URL )

        else:
            return '<img width="100" src="%s" />' % obj.icon_path()
        
    icon.short_description = u'Ikona'
    icon.allow_tags = True

    def select_button(self, obj):
        return """<button ref="%d" name="%s" addr="%s" class="insert-button">Wstaw </button>""" \
                    % (obj.id, obj.filename, obj.static_file.url)
    select_button.allow_tags = True

    def save_form(self, request, form, change):
        obj = super( FileAdmin, self).save_form(request, form, change)
        if 'static_file' in request.FILES:
            obj.filename = request.FILES['static_file'].name
            img = Image.open(request.FILES['static_file'])
            obj.width = img.size[0]
            obj.height = img.size[1]
            
        if not change:
            obj.author = request.user
        return obj
        obj.save()

    def get_urls(self):
        urls = super(FileAdmin, self).get_urls()
        urls = patterns('',
            (r'^popuplist/(?P<media_type>\w+)/$', self.popup_list_view),
        ) + urls
        return urls

    def popup_list_view(self, request, media_type, extra_context=None):
        if not self.has_change_permission(request):
            raise PermissionDenied
        
        def queryset_modifier(queryset):
            if media_type == 'image':
                queryset = queryset.images()
            elif media_type == 'video':
                queryset = queryset.videos()
            return queryset
        
        list_display = ['select_button'] + list(self.list_display)
        return self.simple_list_view(request, extra_context, list_display=list_display, 
                                     template_path=self.change_list_template, 
                                     queryset_modifier=queryset_modifier)

    def save_model(self, request, obj, form, change):
        if change == False and request.POST['_saveasnew'] == 'Zapisz jako nowe':  
            path_info = request.META['HTTP_REFERER']
            id = path_info.split('/')[-2:-1]    #old image id - table of size 1  
            s_file = StaticFile.objects.get(pk = int(id[0]))    
            path = generate_file_path(None, request.POST['filename'])
            old_path = s_file.static_file
            img_path = 'uploads/'+str(old_path)
            result = urllib.urlretrieve(img_path)
            if request.POST['crop_coords'] != "":
                crop_coords = map(int, request.POST['crop_coords'].split(','))
                img = Image.open(result[0])
                cropped_img = img.crop((crop_coords[0], crop_coords[1], crop_coords[0]+ crop_coords[2], crop_coords[1] + crop_coords[3]))
                cropped_img.save('uploads/'+path)
                obj.width, obj.height = cropped_img.size
                obj.crop_coords = ''
            else:
                img = Image.open(result[0])
                img.save('uploads/'+path)
                obj.width, obj.height = img.size
            obj.static_file.save('uploads/'+path,File(open('uploads/'+path)))
            obj.user = request.user
            obj.save()

        else:
            return super(FileAdmin, self).save_model(request, obj, form, change)   

class ProxyAdmin(FileAdmin):
    change_form_template='filemanager/multiupload.html'
    fields = ('category','image_author','description',)

class FileCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', )

admin.site.register(StaticFile, FileAdmin)
admin.site.register(FileCategory, FileCategoryAdmin)
admin.site.register(ProxyModel, ProxyAdmin)
