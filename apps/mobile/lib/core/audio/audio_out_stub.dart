import 'dart:typed_data';

import 'audio_out.dart';

class _SilentAudioOut implements AudioOut {
  @override
  Future<void> init() async {}
  @override
  void feed(Uint8List pcm16) {}
  @override
  void flush() {}
  @override
  double get level => 0;
  @override
  Future<void> dispose() async {}
}

AudioOut createAudioOut() => _SilentAudioOut();
