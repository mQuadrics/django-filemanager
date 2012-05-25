#coding: utf-8

from __future__ import absolute_import
import commands

import os
import base64
import mimetypes

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.db.models.signals import post_save
from django.dispatch.dispatcher import receiver
from .fields import ImageField

from .settings import ICONS_PATH_FORMAT_STR, AVAILABLE_ICONS, IMAGE_ICON_NAME, IMAGE_ICONS
import math

def generate_file_path(instance, filename):
    
    # Get last ID
    filename_id = StaticFile.objects.values_list('id', flat=True).order_by('-id')[0]
    
    filename_ext = filename.split('.')[-1].lower()
    
    container_id = int(math.ceil(float(filename_id) / 1000) * 1000)
    
#    print filename_id
#    print container_id
#    
    filename = str(container_id)+ '/' + str(filename_id) + '.' + filename_ext
    
    #filename_dict = {'filename': filename}
    #filename = filename_dict['filename']
    
    return filename

class FileCategory(models.Model):
    create_time = models.DateTimeField(auto_now_add=True)
    update_time = models.DateTimeField(auto_now=True)
    name = models.CharField(u"Nazwa", max_length=200, help_text=u"Format: rrrr-mm-dd_nazwa_galerii")
    
    class Meta:
        verbose_name = u"Kategoria pliku"
        verbose_name_plural = u"Kategorie plików"
    
    def __unicode__(self):
        return self.name


class StaticFileQueryset(models.query.QuerySet):
    def images(self):
        return self.filter(
            reduce(lambda x, y: x | Q(filename__iendswith=y), StaticFile.IMAGE_EXTENSIONS, Q()))

    def videos(self):
        return self.filter(
            reduce(lambda x, y: x | Q(filename__iendswith=y), StaticFile.VIDEO_EXTENSIONS, Q()))

class StaticFileManager(models.Manager):
    def get_query_set(self):
        return StaticFileQueryset(self.model, using=self._db)

    def images(self):
        return self.all().images()

    def videos(self):
        return self.all().videos()

class StaticFile(models.Model):
    
    MEDIA_TYPE_VIDEO = 1
    MEDIA_TYPE_IMAGE = 2
    MEDIA_TYPE_MVIDEO = 3
    
    MEDIA_TYPE_CHOICES = (
        (MEDIA_TYPE_VIDEO, u'Video'),
        (MEDIA_TYPE_IMAGE, u'Obraz'),
    )
    
    IMAGE_EXTENSIONS = ['jpg', 'jpeg', 'gif', 'png', 'bmp']
    VIDEO_EXTENSIONS = ['flv']
    
    create_time = models.DateTimeField(u'stworzony', auto_now_add=True)
    update_time = models.DateTimeField(auto_now=True)
    author = models.ForeignKey(User, null=True, blank=True)
    category = models.ForeignKey(FileCategory, verbose_name=u"Kategoria pliku", null=True)
    image_author = models.CharField(null=True, blank=True, verbose_name="Autor", max_length=128,)
    
    static_file = models.FileField(u"Plik", upload_to=generate_file_path, blank=True)

    static_file_thumbnail = ImageField(to='self', verbose_name=u'Miniaturka dla pliku video', blank=True, null=True)

    filename = models.CharField(u'Oryginalna nazwa pliku', max_length=100, blank=True,
                                help_text=u'Przy dodawaniu pliku nazwa zapisze się samoczynnie')
    description = models.CharField(u'Krótki opis', max_length=200,
                                   help_text=u'Wyświetlany w nazwie linka')
    
    width = models.IntegerField(u"Szerokość")
    height = models.IntegerField(u"Długość")
    type = models.SmallIntegerField(u'Typ', choices=MEDIA_TYPE_CHOICES, default=MEDIA_TYPE_IMAGE,
            db_index=True)
    crop_coords = models.CharField(u"Współrzędne przycięcia", max_length=100, blank=True,
                                   help_text=u"Wypełniane na żywo podczas przycinania obrazka.")
    
    file_version = models.IntegerField(default=0,)
    objects = StaticFileManager()

    class Meta:
        verbose_name = u"Zdjęcie"
        verbose_name_plural = u"Zdjęcia"
        
    def __unicode__(self):
        return "%s - %s" % (unicode(self.static_file), self.filename)

    def is_image(self):
        if self.file_ext() in StaticFile.IMAGE_EXTENSIONS:
            return True
        return False

    def is_video(self):
        if self.file_ext() in StaticFile.VIDEO_EXTENSIONS:
            return True
        return False

    def file_ext(self):
        try:
            return self.filename.split('.')[-1].lower()
        except IndexError:
            return ''
    file_ext.short_description = "Rozszerzenie pliku"
    

    def image_path(self, size, crop=None):
        params = str(size)
        params += ',%s' % str(self.file_version)
        if crop:    
            params += ',%s' % crop 
            
        return reverse('filemanager.serve_img', kwargs={'file_id': self.id,
            'params': params, 'ext': self.file_ext()})

    def url(self):
        if self.static_file_thumbnail:
            return self.static_file_thumbnail.image_path(1)

        return self.static_file.storage.url(str(self.static_file))

    def as_base64(self):
        with open(self.file_path, "rb") as f:
            encoded_string = base64.b64encode(f.read())
        return 'data:%s;base64,%s' % (mimetypes.guess_type(self.file_path)[0], encoded_string)

    def icon_path(self):
        ext = self.file_ext()
        if ext in AVAILABLE_ICONS:
            return ICONS_PATH_FORMAT_STR % ext
        elif ext in IMAGE_ICONS:
            return reverse('filemanager.serve_img', kwargs={'file_id': self.id, 
                'params': '1', 'ext': self.file_ext()})
            return self.url()
        else:
            return self.url()

    def size(self):
        if os.path.exists(self.file_path):
            return "%0.1f KB" % (os.path.getsize(self.file_path)/(1024.0))
        return "0 MB"

    @property
    def file_path(self):
        return '%s/%s' % (settings.MEDIA_ROOT, self.static_file.name.split("/")[-1])
    
    def make_thumbnail(self):
        originalname = 'thumbnail.png'
        thumbnailfilename = generate_file_path(None, originalname)
        thumbnailfilepath = '%s/%s' % (settings.MEDIA_ROOT, thumbnailfilename)

        StaticFile()
        cmd = "ffmpeg -y -i %s -vframes 1 -ss 00:00:02 -an -vcodec png -f rawvideo %s" %\
              ( self.static_file.path, thumbnailfilepath )

        result = commands.getoutput(cmd)
        obj = StaticFile()
        
        obj.category_id = self.category_id
        obj.static_file = thumbnailfilename
        obj.filename = originalname
        obj.save()

        self.static_file_thumbnail = obj
        self.save()
        

    def save(self, force_insert=False, force_update=False, using=None):
        self.file_version = self.file_version + 1
        super(StaticFile, self).save(force_insert, force_update, using)

    
class ProxyModel(StaticFile):
    class Meta:
        proxy = True

            
@receiver(post_save, sender=StaticFile)
def thumbnailer(sender, **kwargs):
    obj = kwargs['instance']
    if kwargs['created'] and 'flv' == obj.file_ext() and not obj.static_file_thumbnail :
        obj.make_thumbnail()