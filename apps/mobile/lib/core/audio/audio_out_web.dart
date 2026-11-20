import 'dart:js_interop';
import 'dart:typed_data';

import 'package:web/web.dart' as web;

import 'audio_out.dart';

/// Web Audio player: each chunk becomes an AudioBuffer scheduled right after the previous one.
class _WebAudioOut implements AudioOut {
  web.AudioContext? _ctx;
  double _nextStart = 0;
  final List<web.AudioBufferSourceNode> _playing = [];
  final List<(double start, double end, double level)> _levels = [];

  @override
  Future<void> init() async {
    _ctx ??= web.AudioContext(web.AudioContextOptions(sampleRate: AudioOut.sampleRate));
    // Browsers keep audio suspended until a user gesture; init() is called from a tap.
    await _ctx!.resume().toDart;
  }

  @override
  void feed(Uint8List pcm16) {
    final ctx = _ctx;
    if (ctx == null || pcm16.lengthInBytes < 2) return;
    final n = pcm16.lengthInBytes ~/ 2;
    final data = ByteData.sublistView(pcm16);
    final samples = Float32List(n);
    for (var i = 0; i < n; i++) {
      samples[i] = data.getInt16(i * 2, Endian.little) / 32768.0;
    }
    final buffer = ctx.createBuffer(1, n, AudioOut.sampleRate);
    buffer.copyToChannel(samples.toJS, 0);
    final source = ctx.createBufferSource()..buffer = buffer;
    source.connect(ctx.destination);
    final now = ctx.currentTime;
    if (_nextStart < now + 0.02) _nextStart = now + 0.04; // small cushion after a gap
    source.start(_nextStart);
    final end = _nextStart + n / AudioOut.sampleRate;
    _levels.add((_nextStart, end, pcmLevel(pcm16)));
    _nextStart = end;
    _playing.add(source);
    if (_playing.length > 64) _playing.removeRange(0, _playing.length - 64);
    if (_levels.length > 64) _levels.removeRange(0, _levels.length - 64);
  }

  @override
  void flush() {
    for (final s in _playing) {
      try {
        s.stop();
      } catch (_) {
        // already ended
      }
    }
    _playing.clear();
    _levels.clear();
    _nextStart = 0;
  }

  @override
  double get level {
    final ctx = _ctx;
    if (ctx == null) return 0;
    final now = ctx.currentTime;
    for (final (start, end, level) in _levels) {
      if (now >= start && now < end) return level;
    }
    return 0;
  }

  @override
  Future<void> dispose() async {
    flush();
    final ctx = _ctx;
    _ctx = null;
    if (ctx != null) await ctx.close().toDart;
  }
}

AudioOut createAudioOut() => _WebAudioOut();
