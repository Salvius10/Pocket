import 'dart:async';
import 'dart:typed_data';

import 'package:record/record.dart';

/// Microphone for the mascot: PCM16 LE mono at 16 kHz with echo cancellation on, streamed in
/// small chunks. The only file that imports `record` (7.2.0).
class AudioIn {
  static const sampleRate = 16000;
  final AudioRecorder _recorder = AudioRecorder();
  StreamSubscription<Uint8List>? _sub;

  bool get isRecording => _sub != null;

  /// Asks for the mic if needed. Returns false when the user or the browser says no.
  Future<bool> start(void Function(Uint8List pcm16) onChunk) async {
    if (_sub != null) return true;
    if (!await _recorder.hasPermission()) return false;
    final stream = await _recorder.startStream(const RecordConfig(
      encoder: AudioEncoder.pcm16bits,
      sampleRate: sampleRate,
      numChannels: 1,
      echoCancel: true,
      noiseSuppress: true,
      autoGain: true,
    ));
    _sub = stream.listen(onChunk, onError: (_) => stop());
    return true;
  }

  Future<void> stop() async {
    final sub = _sub;
    _sub = null;
    await sub?.cancel();
    await _recorder.stop();
  }

  Future<void> dispose() async {
    await stop();
    await _recorder.dispose();
  }
}
