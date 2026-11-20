import 'dart:typed_data';

import 'package:flutter_pcm_sound/flutter_pcm_sound.dart';

import 'audio_out.dart';

/// Android player on flutter_pcm_sound 3.3.3 (setup / feed / release).
class _PcmSoundAudioOut implements AudioOut {
  bool _ready = false;
  double _level = 0;
  DateTime _levelAt = DateTime.fromMillisecondsSinceEpoch(0);
  int _epoch = 0;

  @override
  Future<void> init() async {
    if (_ready) return;
    await FlutterPcmSound.setup(sampleRate: AudioOut.sampleRate, channelCount: 1);
    await FlutterPcmSound.setFeedThreshold(AudioOut.sampleRate ~/ 10);
    _ready = true;
  }

  @override
  void feed(Uint8List pcm16) {
    if (!_ready || pcm16.lengthInBytes < 2) return;
    final epoch = _epoch;
    _level = pcmLevel(pcm16);
    _levelAt = DateTime.now();
    final copy = Uint8List.fromList(pcm16); // PCM16 little endian, which is the host order on Android
    if (epoch == _epoch) FlutterPcmSound.feed(PcmArrayInt16(bytes: ByteData.sublistView(copy)));
  }

  @override
  void flush() {
    // The plugin has no "clear queue"; releasing and setting up again drops what is buffered.
    _epoch++;
    _level = 0;
    if (!_ready) return;
    _ready = false;
    FlutterPcmSound.release().then((_) => init());
  }

  @override
  double get level => DateTime.now().difference(_levelAt) < const Duration(milliseconds: 260) ? _level : 0;

  @override
  Future<void> dispose() async {
    _ready = false;
    await FlutterPcmSound.release();
  }
}

AudioOut createAudioOut() => _PcmSoundAudioOut();
