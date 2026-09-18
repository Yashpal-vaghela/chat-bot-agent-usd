from django.contrib import admin
from .models import VoiceRecordingLog

@admin.register(VoiceRecordingLog)
class VoiceRecordingLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'conversation_type', 'save_type', 'rating', 'created_at', 'audio_file')
    list_filter = ('conversation_type', 'save_type', 'created_at')
    search_fields = ('transcript', 'rating', 'call_id')
    readonly_fields = ('created_at',)


