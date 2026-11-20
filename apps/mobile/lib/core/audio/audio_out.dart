import 'dart:math' as math;
import 'dart:typed_data';

import 'audio_out_stub.dart' if (dart.library.js_interop) 'audio_out_web.dart' if (dart.library.io) 'audio_out_io.dart' as impl;

/// Speaker for the mascot: PCM16 LE mono at 24 kHz, as the agent sends it.
///
/// One interface, two players behind it: `flutter_pcm_sound` on Android and a small Web Audio
/// player in browsers (flutter_pcm_sound does not run there). Nothing else imports either.
abstract class AudioOut {
  static const sampleRate = 24000;

  Future<void> init();

  /// Queue one chunk for playback.
  void feed(Uint8List pcm16);

  /// Drop everything queued (on `interrupted` and `stop_audio`).
  void flush();

  /// Loudness of what is playing right now, 0..1. Drives the mascot's mouth.
  double get level;

  Future<void> dispose();
}

AudioOut createAudioOut() => impl.createAudioOut();

/// RMS of a PCM16 chunk, scaled so normal speech lands around 0.3-0.8.
double pcmLevel(Uint8List pcm16) {
  if (pcm16.lengthInBytes < 2) return 0;
  final data = ByteData.sublistView(pcm16);
  final n = pcm16.lengthInBytes ~/ 2;
  final step = math.max(1, n ~/ 240);
  double sum = 0;
  var count = 0;
  for (var i = 0; i < n; i += step) {
    final v = data.getInt16(i * 2, Endian.little) / 32768.0;
    sum += v * v;
    count++;
  }
  return (math.sqrt(sum / count) * 4.2).clamp(0.0, 1.0);
}
