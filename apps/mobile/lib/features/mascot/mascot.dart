import 'dart:math' as math;
import 'dart:ui' as ui;

import 'package:flutter/scheduler.dart';
import 'package:material_ui/material_ui.dart';

import '../../core/theme.dart';
import 'rive_mascot.dart';

/// The eight moods of the mascot. Same names as the Rive `MascotVM.mood` enum.
enum MascotMood { idle, listening, thinking, talking, happy, concerned, celebrating, sleepy }

MascotMood moodFromName(String? name) =>
    MascotMood.values.firstWhere((m) => m.name == name, orElse: () => MascotMood.idle);

/// The mascot's inputs. This is the `MascotVM` contract (BUILD_PLAN M8):
/// `mood` enum, `mouthOpen` 0-100, `blink` trigger, `lookX` / `lookY` -1..1.
/// Both the Rive mascot and the painted fallback are driven by this one object.
class MascotController extends ChangeNotifier {
  MascotMood _mood = MascotMood.idle;
  double _mouthOpen = 0;
  double lookX = 0;
  double lookY = 0;
  int blinkCount = 0;
  DateTime _mouthAt = DateTime.fromMillisecondsSinceEpoch(0);

  MascotMood get mood => _mood;
  double get mouthOpen => _mouthOpen;

  /// True while real audio levels are arriving, so lip-sync follows the speaker.
  bool get hasLiveMouth => DateTime.now().difference(_mouthAt) < const Duration(milliseconds: 220);

  set mood(MascotMood value) {
    if (value == _mood) return;
    _mood = value;
    notifyListeners();
  }

  /// 0-100, from playback RMS.
  void setMouthOpen(double value) {
    _mouthOpen = value.clamp(0, 100).toDouble();
    _mouthAt = DateTime.now();
  }

  void blink() {
    blinkCount++;
    notifyListeners();
  }

  void look(double x, double y) {
    lookX = x.clamp(-1, 1).toDouble();
    lookY = y.clamp(-1, 1).toDouble();
  }
}

/// Poko. Uses the designer's Rive file when it is bundled, otherwise the painted fallback.
class Mascot extends StatelessWidget {
  const Mascot({super.key, required this.controller, this.size = 160});
  final MascotController controller;
  final double size;

  @override
  Widget build(BuildContext context) {
    return RiveMascot.maybeBuild(controller: controller, size: size) ?? FallbackMascot(controller: controller, size: size);
  }
}

/// A pocket with a coin peeking out, drawn in code. It is the app's mark as well as its voice.
class FallbackMascot extends StatefulWidget {
  const FallbackMascot({super.key, required this.controller, this.size = 160});
  final MascotController controller;
  final double size;

  @override
  State<FallbackMascot> createState() => _FallbackMascotState();
}

class _Pose {
  double eyeOpen = 1, eyeArc = 0, smile = 0.35, coinRise = 8, tilt = 0, brow = 0, cheek = 0, dim = 0, lift = 0, mouth = 0, lookX = 0, lookY = 0;
}

class _FallbackMascotState extends State<FallbackMascot> with SingleTickerProviderStateMixin {
  late final Ticker _ticker;
  final _pose = _Pose();
  double _t = 0;
  double _lastTick = 0;
  double _nextBlink = 2.4;
  double _blinkT = -1;
  int _seenBlink = 0;
  final _rand = math.Random(7);

  @override
  void initState() {
    super.initState();
    _seenBlink = widget.controller.blinkCount;
    _ticker = createTicker(_onTick)..start();
  }

  @override
  void dispose() {
    _ticker.dispose();
    super.dispose();
  }

  _Pose _target(MascotMood mood) {
    final p = _Pose();
    switch (mood) {
      case MascotMood.idle:
        break;
      case MascotMood.listening:
        p..eyeOpen = 1.14..smile = 0.2..coinRise = 17..tilt = -0.05;
      case MascotMood.thinking:
        p..eyeOpen = 0.86..smile = 0..coinRise = 12..tilt = 0.035..brow = 0.25..lookX = -0.6..lookY = -0.8;
      case MascotMood.talking:
        p..smile = 0.3..coinRise = 10;
      case MascotMood.happy:
        p..eyeArc = 1..smile = 0.95..coinRise = 20..cheek = 0.85;
      case MascotMood.concerned:
        p..eyeOpen = 0.92..smile = -0.6..coinRise = 1..brow = 1..lift = 3;
      case MascotMood.celebrating:
        p..eyeArc = 1..smile = 1..coinRise = 28..cheek = 1;
      case MascotMood.sleepy:
        p..eyeOpen = 0.1..smile = 0.1..coinRise = -9..tilt = 0.04..dim = 0.5..lift = 3;
    }
    return p;
  }

  void _onTick(Duration elapsed) {
    final now = elapsed.inMicroseconds / 1e6;
    final dt = (now - _lastTick).clamp(0.0, 0.05);
    _lastTick = now;
    _t = now;
    final c = widget.controller;
    final target = _target(c.mood);
    // Critically-damped approach: quick to start, soft to land, always interruptible.
    final k = 1 - math.exp(-dt * 11);
    double go(double from, double to) => from + (to - from) * k;
    _pose
      ..eyeOpen = go(_pose.eyeOpen, target.eyeOpen)
      ..eyeArc = go(_pose.eyeArc, target.eyeArc)
      ..smile = go(_pose.smile, target.smile)
      ..coinRise = go(_pose.coinRise, target.coinRise)
      ..tilt = go(_pose.tilt, target.tilt)
      ..brow = go(_pose.brow, target.brow)
      ..cheek = go(_pose.cheek, target.cheek)
      ..dim = go(_pose.dim, target.dim)
      ..lift = go(_pose.lift, target.lift)
      ..lookX = go(_pose.lookX, c.mood == MascotMood.thinking ? target.lookX : c.lookX)
      ..lookY = go(_pose.lookY, c.mood == MascotMood.thinking ? target.lookY : c.lookY);

    // Mouth: follow real audio when it is there; otherwise a believable talking pattern.
    double mouthTarget = 0;
    if (c.mood == MascotMood.talking) {
      mouthTarget = c.hasLiveMouth
          ? c.mouthOpen / 100
          : (0.2 + 0.55 * (math.sin(_t * 13.0) * math.sin(_t * 4.3 + 1.0)).abs() + 0.12 * math.sin(_t * 29.0)).clamp(0.0, 1.0);
    } else if (c.hasLiveMouth) {
      mouthTarget = c.mouthOpen / 100;
    }
    _pose.mouth += (mouthTarget - _pose.mouth) * (1 - math.exp(-dt * 26));

    // Blinks: on a loose timer, or when the trigger fires.
    if (c.blinkCount != _seenBlink) {
      _seenBlink = c.blinkCount;
      _blinkT = 0;
    }
    if (_blinkT < 0 && _t > _nextBlink && c.mood != MascotMood.sleepy) {
      _blinkT = 0;
      _nextBlink = _t + 2.2 + _rand.nextDouble() * 3.2;
    }
    if (_blinkT >= 0) {
      _blinkT += dt;
      if (_blinkT > 0.16) _blinkT = -1;
    }
    if (mounted) setState(() {});
  }

  @override
  Widget build(BuildContext context) {
    final blink = _blinkT < 0 ? 0.0 : math.sin((_blinkT / 0.16) * math.pi);
    return Semantics(
      label: 'Poko',
      image: true,
      child: RepaintBoundary(
        child: SizedBox(
          width: widget.size,
          height: widget.size,
          child: CustomPaint(painter: _PokoPainter(pose: _pose, t: _t, blink: blink, mood: widget.controller.mood)),
        ),
      ),
    );
  }
}

class _PokoPainter extends CustomPainter {
  _PokoPainter({required this.pose, required this.t, required this.blink, required this.mood});
  final _Pose pose;
  final double t;
  final double blink;
  final MascotMood mood;

  static const _lime = Pk.lime;
  static const _shade = Color(0xFF394714);
  static const _hem = Color(0xFFB4DC55);
  static const _ink = Color(0xFF12140D);
  static const _coin = Color(0xFFF2CC6B);
  static const _coinEdge = Color(0xFFB98F2E);

  Path _body() {
    const l = 38.0, r = 162.0, top = 64.0, c = 12.0;
    return Path()
      ..moveTo(l + c, top)
      ..lineTo(r - c, top)
      ..quadraticBezierTo(r, top, r, top + c)
      ..lineTo(r, 126)
      ..quadraticBezierTo(r - 1, 158, 114, 175)
      ..quadraticBezierTo(100, 181, 86, 175)
      ..quadraticBezierTo(l + 1, 158, l, 126)
      ..lineTo(l, top + c)
      ..quadraticBezierTo(l, top, l + c, top)
      ..close();
  }

  Path _stitch() {
    const l = 47.0, r = 153.0, top = 92.0;
    return Path()
      ..moveTo(l, top)
      ..lineTo(l, 125)
      ..quadraticBezierTo(l + 2, 151, 89, 166)
      ..quadraticBezierTo(100, 170.5, 111, 166)
      ..quadraticBezierTo(r - 2, 151, r, 125)
      ..lineTo(r, top);
  }

  void _dashed(Canvas canvas, Path path, Paint paint, {double dash = 6, double gap = 5}) {
    for (final metric in path.computeMetrics()) {
      double d = 0;
      while (d < metric.length) {
        canvas.drawPath(metric.extractPath(d, math.min(d + dash, metric.length)), paint);
        d += dash + gap;
      }
    }
  }

  @override
  void paint(Canvas canvas, Size size) {
    final s = size.width / 200;
    canvas.scale(s);
    final breathe = math.sin(t * 2.1) * 0.012;
    final hop = mood == MascotMood.celebrating ? -9 * math.sin(t * 7.5).abs() : 0.0;
    final talkBob = pose.mouth * 1.6;

    // Everything pivots around the bottom of the pocket.
    canvas.translate(100, 178);
    canvas.rotate(pose.tilt + (mood == MascotMood.listening ? math.sin(t * 2.6) * 0.012 : 0));
    canvas.scale(1 - breathe * 0.6, 1 + breathe);
    canvas.translate(-100, -178 + pose.lift + hop - talkBob);

    final body = _body();

    // Hard offset shadow: the brutalist bit.
    canvas.drawPath(body.shift(const Offset(7, 7)), Paint()..color = _shade);

    _drawExtrasBehind(canvas);
    _drawCoin(canvas);

    // Pocket.
    canvas.drawPath(body, Paint()..color = _lime);
    canvas.save();
    canvas.clipPath(body);
    canvas.drawRect(const Rect.fromLTWH(30, 60, 140, 21), Paint()..color = _hem);
    canvas.restore();
    canvas.drawLine(const Offset(38, 81), const Offset(162, 81), Paint()..color = _ink.withValues(alpha: 0.28)..strokeWidth = 1.6);
    _dashed(
      canvas,
      Path()..moveTo(47, 72.5)..lineTo(153, 72.5),
      Paint()..color = _ink.withValues(alpha: 0.42)..strokeWidth = 1.8..style = PaintingStyle.stroke..strokeCap = StrokeCap.round,
    );
    _dashed(
      canvas,
      _stitch(),
      Paint()..color = _ink.withValues(alpha: 0.42)..strokeWidth = 1.8..style = PaintingStyle.stroke..strokeCap = StrokeCap.round,
    );
    canvas.drawPath(body, Paint()..color = _ink..style = PaintingStyle.stroke..strokeWidth = 3.2..strokeJoin = StrokeJoin.round);

    _drawFace(canvas);

    if (pose.dim > 0.01) {
      canvas.drawPath(body, Paint()..color = Pk.ink.withValues(alpha: pose.dim * 0.55));
    }
    _drawExtrasFront(canvas);
  }

  void _drawCoin(Canvas canvas) {
    final bob = math.sin(t * 2.1 + 1) * 1.5;
    final cy = 66 - pose.coinRise - bob;
    final spin = mood == MascotMood.thinking ? math.cos(t * 4.2) : 1.0;
    canvas.save();
    canvas.translate(100, cy);
    canvas.scale(spin.abs().clamp(0.08, 1.0), 1);
    canvas.drawCircle(Offset.zero, 26, Paint()..color = _coin);
    canvas.drawCircle(Offset.zero, 26, Paint()..color = _ink..style = PaintingStyle.stroke..strokeWidth = 3.2);
    canvas.drawCircle(Offset.zero, 19.5, Paint()..color = _coinEdge..style = PaintingStyle.stroke..strokeWidth = 1.6);
    if (spin.abs() > 0.3) {
      final tp = TextPainter(
        text: const TextSpan(text: '₹', style: TextStyle(fontFamily: Pk.mono, fontWeight: FontWeight.w600, fontSize: 25, color: _ink, height: 1)),
        textDirection: TextDirection.ltr,
      )..layout();
      tp.paint(canvas, Offset(-tp.width / 2, -tp.height / 2 - 0.5));
    }
    canvas.restore();
  }

  void _drawFace(Canvas canvas) {
    final ink = Paint()..color = _ink;
    final lx = pose.lookX * 4.5, ly = pose.lookY * 3.2;
    final open = (pose.eyeOpen * (1 - blink)).clamp(0.06, 1.25);
    const ey = 114.0;

    for (final ex in [78.0, 122.0]) {
      final cx = ex + lx, cy = ey + ly;
      if (pose.eyeArc > 0.5) {
        // Smiling eyes: an upward arc.
        final arc = Path()
          ..moveTo(cx - 8.5, cy + 3)
          ..quadraticBezierTo(cx, cy - 8.5, cx + 8.5, cy + 3);
        canvas.drawPath(arc, Paint()..color = _ink..style = PaintingStyle.stroke..strokeWidth = 4.2..strokeCap = StrokeCap.round);
      } else {
        final h = 21.0 * open;
        canvas.drawRRect(RRect.fromRectAndRadius(Rect.fromCenter(center: Offset(cx, cy), width: 13.5, height: math.max(h, 3.2)), const Radius.circular(6.75)), ink);
        if (open > 0.6) {
          canvas.drawCircle(Offset(cx + 2.4, cy - h * 0.22), 2.3, Paint()..color = const Color(0xFFF6FBE4));
        }
      }
    }

    if (pose.brow > 0.02) {
      final p = Paint()..color = _ink.withValues(alpha: pose.brow.clamp(0, 1))..style = PaintingStyle.stroke..strokeWidth = 3.4..strokeCap = StrokeCap.round;
      final rise = 5.5 * pose.brow;
      canvas.drawLine(Offset(69 + lx, 97 + ly), Offset(86 + lx, 97 - rise + ly), p);
      canvas.drawLine(Offset(131 + lx, 97 + ly), Offset(114 + lx, 97 - rise + ly), p);
    }

    if (pose.cheek > 0.02) {
      final p = Paint()..color = Pk.coral.withValues(alpha: 0.55 * pose.cheek);
      canvas.drawOval(Rect.fromCenter(center: const Offset(62, 131), width: 13, height: 8), p);
      canvas.drawOval(Rect.fromCenter(center: const Offset(138, 131), width: 13, height: 8), p);
    }

    const my = 141.0;
    final m = pose.mouth;
    if (m > 0.06) {
      final w = 21 - 5 * m, h = 5 + 15 * m;
      final rect = Rect.fromCenter(center: Offset(100, my + h * 0.2), width: w, height: h);
      canvas.drawRRect(RRect.fromRectAndRadius(rect, Radius.circular(math.min(w, h) / 2)), ink);
      if (m > 0.45) {
        canvas.save();
        canvas.clipRRect(RRect.fromRectAndRadius(rect, Radius.circular(math.min(w, h) / 2)));
        canvas.drawOval(Rect.fromCenter(center: Offset(100, rect.bottom + 1), width: w * 0.9, height: h * 0.7), Paint()..color = Pk.coral);
        canvas.restore();
      }
    } else {
      final curve = Path()
        ..moveTo(88, my - pose.smile * 2)
        ..quadraticBezierTo(100, my + pose.smile * 10, 112, my - pose.smile * 2);
      canvas.drawPath(curve, Paint()..color = _ink..style = PaintingStyle.stroke..strokeWidth = 3.6..strokeCap = StrokeCap.round);
    }
  }

  void _drawExtrasBehind(Canvas canvas) {
    if (mood == MascotMood.celebrating) {
      // Little coins and confetti tossed up from the pocket.
      for (var i = 0; i < 7; i++) {
        final phase = (t * 0.9 + i * 0.143) % 1.0;
        final angle = -math.pi / 2 + (i - 3) * 0.33;
        final dist = 26 + phase * 62;
        final x = 100 + math.cos(angle) * dist;
        final y = 44 + math.sin(angle) * dist + phase * phase * 46;
        final a = (1 - phase).clamp(0.0, 1.0);
        final color = [_coin, Pk.lime, Pk.bone, Pk.coral][i % 4].withValues(alpha: a);
        if (i.isEven) {
          canvas.drawCircle(Offset(x, y), 4.2, Paint()..color = color);
        } else {
          canvas.save();
          canvas.translate(x, y);
          canvas.rotate(phase * 5 + i);
          canvas.drawRect(const Rect.fromLTWH(-3.5, -3.5, 7, 7), Paint()..color = color);
          canvas.restore();
        }
      }
    }
  }

  void _drawExtrasFront(Canvas canvas) {
    if (mood == MascotMood.listening) {
      // Sound arcs on both sides, breathing outward.
      for (var i = 0; i < 2; i++) {
        final phase = (t * 1.5 + i * 0.5) % 1.0;
        final p = Paint()
          ..color = Pk.bone.withValues(alpha: (1 - phase) * 0.75)
          ..style = PaintingStyle.stroke
          ..strokeWidth = 2.6
          ..strokeCap = StrokeCap.round;
        final r = 14 + phase * 13;
        canvas.drawArc(Rect.fromCircle(center: const Offset(176, 108), radius: r), -0.75, 1.5, false, p);
        canvas.drawArc(Rect.fromCircle(center: const Offset(24, 108), radius: r), math.pi - 0.75, 1.5, false, p);
      }
    } else if (mood == MascotMood.thinking) {
      for (var i = 0; i < 3; i++) {
        final on = ((t * 2.4).floor() % 3) == i;
        canvas.drawRect(Rect.fromLTWH(150.0 + i * 11, 30.0 - i * 6, 6, 6), Paint()..color = on ? Pk.bone : Pk.lineStrong);
      }
    } else if (mood == MascotMood.sleepy) {
      for (var i = 0; i < 3; i++) {
        final phase = (t * 0.32 + i * 0.33) % 1.0;
        final tp = TextPainter(
          text: TextSpan(
            text: 'z',
            style: TextStyle(fontFamily: Pk.mono, fontWeight: FontWeight.w600, fontSize: 11.0 + phase * 11, color: Pk.muted.withValues(alpha: math.sin(phase * math.pi))),
          ),
          textDirection: TextDirection.ltr,
        )..layout();
        tp.paint(canvas, Offset(146 + phase * 26, 58 - phase * 44));
      }
    }
  }

  @override
  bool shouldRepaint(_PokoPainter old) => true;
}

/// A still mark of Poko for places that should not animate (app bar, loaders).
class PokoMark extends StatelessWidget {
  const PokoMark({super.key, this.size = 28, this.mood = MascotMood.idle});
  final double size;
  final MascotMood mood;

  @override
  Widget build(BuildContext context) {
    final pose = _Pose();
    if (mood == MascotMood.happy) {
      pose..eyeArc = 1..smile = 0.9..coinRise = 16;
    } else if (mood == MascotMood.sleepy) {
      pose..eyeOpen = 0.1..coinRise = -8..dim = 0.5;
    }
    return SizedBox(width: size, height: size, child: CustomPaint(painter: _PokoPainter(pose: pose, t: 0, blink: 0, mood: MascotMood.idle)));
  }
}

// Keeps `dart:ui` referenced for PathMetric on all platforms.
typedef PokoPathMetric = ui.PathMetric;
