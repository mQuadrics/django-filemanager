#coding: utf-8

from __future__ import absolute_import

from django import forms

from .models import StaticFile

class StaticFileForm(forms.models.ModelForm):
    class Meta:
        model = StaticFile
        fields = ('author', 'category', 'filename', 'description','width','height', 'static_file')
