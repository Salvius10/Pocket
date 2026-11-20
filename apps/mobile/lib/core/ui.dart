import 'dart:math' as math;

import 'package:material_ui/material_ui.dart';

import 'theme.dart';

/// Tappable wrapper with tactile feedback: a slight scale-down on press.
/// Hit area is at least 44px even when the child is smaller.
class Pressable extends StatefulWidget {
  const Pressable({super.key, required this.child, this.onTap, this.onLongPress, this.scale = 0.97, this.semantics, this.disabled = false});
  final Widget child;
  final VoidCallback? onTap;
  final VoidCallback? onLongPress;
  final double scale;
  final String? semantics;

  /// Shows the dimmed "can't use this right now" look. A plain non-tappable row is not disabled.
  final bool disabled;

  @override
  State<Pressable> createState() => _PressableState();
}

class _PressableState extends State<Pressable> {
  bool _down = false;

  void _set(bool v) {
    if (_down != v && mounted) setState(() => _down = v);
  }

  @override
  Widget build(BuildContext context) {
    final enabled = widget.onTap != null || widget.onLongPress != null;
    return Semantics(
      button: enabled,
      label: widget.semantics,
      child: MouseRegion(
        cursor: enabled ? SystemMouseCursors.click : MouseCursor.defer,
        child: GestureDetector(
          behavior: HitTestBehavior.opaque,
          onTapDown: enabled ? (_) => _set(true) : null,
          onTapUp: enabled ? (_) => _set(false) : null,
          onTapCancel: enabled ? () => _set(false) : null,
          onTap: widget.onTap,
          onLongPress: widget.onLongPress,
          child: ConstrainedBox(
            constraints: const BoxConstraints(minHeight: 44),
            child: AnimatedScale(
              scale: _down ? widget.scale : 1,
              duration: Pk.fast,
              curve: Pk.ease,
              child: AnimatedOpacity(opacity: widget.disabled ? 0.45 : 1, duration: Pk.fast, child: widget.child),
            ),
          ),
        ),
      ),
    );
  }
}

/// The primary action. A solid block with a hard offset edge that it presses into.
class BlockButton extends StatefulWidget {
  const BlockButton({super.key, required this.label, this.onTap, this.icon, this.color = Pk.lime, this.onColor = Pk.limeInk, this.expand = true, this.busy = false});
  final String label;
  final VoidCallback? onTap;
  final IconData? icon;
  final Color color;
  final Color onColor;
  final bool expand;
  final bool busy;

  @override
  State<BlockButton> createState() => _BlockButtonState();
}

class _BlockButtonState extends State<BlockButton> {
  bool _down = false;

  @override
  Widget build(BuildContext context) {
    final enabled = widget.onTap != null && !widget.busy;
    const depth = 3.0;
    final face = AnimatedContainer(
      duration: Pk.fast,
      curve: Pk.ease,
      transform: Matrix4.translationValues(_down ? depth : 0, _down ? depth : 0, 0),
      height: 50,
      padding: const EdgeInsets.symmetric(horizontal: 18),
      decoration: BoxDecoration(color: widget.color, borderRadius: BorderRadius.circular(Pk.rSm)),
      child: Row(
        mainAxisSize: widget.expand ? MainAxisSize.max : MainAxisSize.min,
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          if (widget.busy)
            SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2, color: widget.onColor))
          else if (widget.icon != null)
            Icon(widget.icon, size: 18, color: widget.onColor),
          if (widget.busy || widget.icon != null) const SizedBox(width: 10),
          Flexible(
            child: Text(widget.label, maxLines: 1, overflow: TextOverflow.ellipsis, style: Pk.text(15.5, w: FontWeight.w600, c: widget.onColor, ls: 0.1)),
          ),
        ],
      ),
    );
    return Semantics(
      button: true,
      enabled: enabled,
      label: widget.label,
      child: MouseRegion(
        cursor: enabled ? SystemMouseCursors.click : MouseCursor.defer,
        child: GestureDetector(
          onTapDown: enabled ? (_) => setState(() => _down = true) : null,
          onTapUp: enabled ? (_) => setState(() => _down = false) : null,
          onTapCancel: enabled ? () => setState(() => _down = false) : null,
          onTap: enabled ? widget.onTap : null,
          child: Opacity(
            opacity: enabled || widget.busy ? 1 : 0.4,
            child: Padding(
              padding: const EdgeInsets.only(right: depth, bottom: depth),
              child: Stack(
                clipBehavior: Clip.none,
                children: [
                  Positioned(
                    left: depth, top: depth, right: -depth, bottom: -depth,
                    child: DecoratedBox(
                      decoration: BoxDecoration(
                        color: Color.lerp(widget.color, Pk.ink, 0.62),
                        borderRadius: BorderRadius.circular(Pk.rSm),
                      ),
                    ),
                  ),
                  face,
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// Quiet secondary action: outlined, no fill.
class GhostButton extends StatelessWidget {
  const GhostButton({super.key, required this.label, this.onTap, this.icon, this.color = Pk.bone, this.dense = false});
  final String label;
  final VoidCallback? onTap;
  final IconData? icon;
  final Color color;
  final bool dense;

  @override
  Widget build(BuildContext context) {
    return Pressable(
      onTap: onTap,
      semantics: label,
      disabled: onTap == null,
      child: Container(
        height: dense ? 38 : 50,
        padding: EdgeInsets.symmetric(horizontal: dense ? 12 : 18),
        decoration: BoxDecoration(border: Border.all(color: Pk.lineStrong), borderRadius: BorderRadius.circular(Pk.rSm)),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            if (icon != null) ...[Icon(icon, size: dense ? 15 : 18, color: color), const SizedBox(width: 8)],
            Flexible(child: Text(label, maxLines: 1, overflow: TextOverflow.ellipsis, style: Pk.text(dense ? 13.5 : 15, w: FontWeight.w500, c: color))),
          ],
        ),
      ),
    );
  }
}

/// A card: flat surface, real 1px border, tight corners.
class PCard extends StatelessWidget {
  const PCard({super.key, required this.child, this.padding = const EdgeInsets.all(Pk.pad), this.color = Pk.surface, this.border = Pk.line, this.onTap, this.onLongPress});
  final Widget child;
  final EdgeInsetsGeometry padding;
  final Color color;
  final Color border;
  final VoidCallback? onTap;
  final VoidCallback? onLongPress;

  @override
  Widget build(BuildContext context) {
    final box = Container(
      width: double.infinity,
      padding: padding,
      decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(Pk.r), border: Border.all(color: border)),
      child: child,
    );
    if (onTap == null && onLongPress == null) return box;
    return Pressable(onTap: onTap, onLongPress: onLongPress, scale: 0.985, child: box);
  }
}

/// "02 · POCKETS" with an optional trailing action.
class SectionLabel extends StatelessWidget {
  const SectionLabel(this.text, {super.key, this.index, this.trailing, this.color = Pk.muted});
  final String text;
  final int? index;
  final Widget? trailing;
  final Color color;

  @override
  Widget build(BuildContext context) {
    final prefix = index == null ? '' : '${index!.toString().padLeft(2, '0')} · ';
    return Row(
      children: [
        Expanded(child: Text('$prefix${text.toUpperCase()}', maxLines: 1, overflow: TextOverflow.ellipsis, style: Pk.label(c: color))),
        if (trailing != null) trailing!,
      ],
    );
  }
}

/// The stitch: a dashed line, the same one sewn around the mascot's pocket.
class Stitch extends StatelessWidget {
  const Stitch({super.key, this.color = Pk.line, this.vertical = 10});
  final Color color;
  final double vertical;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.symmetric(vertical: vertical),
      child: SizedBox(height: 1, width: double.infinity, child: CustomPaint(painter: _StitchPainter(color))),
    );
  }
}

class _StitchPainter extends CustomPainter {
  _StitchPainter(this.color);
  final Color color;

  @override
  void paint(Canvas canvas, Size size) {
    final p = Paint()
      ..color = color
      ..strokeWidth = 1;
    const dash = 5.0, gap = 4.0;
    for (double x = 0; x < size.width; x += dash + gap) {
      canvas.drawLine(Offset(x, 0.5), Offset(math.min(x + dash, size.width), 0.5), p);
    }
  }

  @override
  bool shouldRepaint(_StitchPainter old) => old.color != color;
}

/// Progress as a row of blocks. Reads at a glance and never pretends to be more precise than it is.
class SegBar extends StatelessWidget {
  const SegBar({super.key, required this.pct, this.color = Pk.lime, this.segments = 20, this.height = 10, this.marker});
  final num pct; // 0..100+, clamps
  final Color color;
  final int segments;
  final double height;
  final double? marker; // 0..1 position of a "today" tick

  @override
  Widget build(BuildContext context) {
    return TweenAnimationBuilder<double>(
      tween: Tween(begin: 0, end: (pct / 100).clamp(0, 1).toDouble()),
      duration: Pk.slow,
      curve: Pk.ease,
      builder: (context, v, _) => SizedBox(
        height: height + (marker == null ? 0 : 5),
        width: double.infinity,
        child: CustomPaint(painter: _SegPainter(v, color, segments, height, marker)),
      ),
    );
  }
}

class _SegPainter extends CustomPainter {
  _SegPainter(this.v, this.color, this.segments, this.h, this.marker);
  final double v;
  final Color color;
  final int segments;
  final double h;
  final double? marker;

  @override
  void paint(Canvas canvas, Size size) {
    const gap = 2.0;
    final w = (size.width - gap * (segments - 1)) / segments;
    final filled = v * segments;
    for (var i = 0; i < segments; i++) {
      final x = i * (w + gap);
      final amount = (filled - i).clamp(0.0, 1.0);
      final rect = RRect.fromRectAndRadius(Rect.fromLTWH(x, 0, w, h), const Radius.circular(1));
      canvas.drawRRect(rect, Paint()..color = Pk.line);
      if (amount > 0) {
        canvas.drawRRect(
          RRect.fromRectAndRadius(Rect.fromLTWH(x, 0, w * amount, h), const Radius.circular(1)),
          Paint()..color = color,
        );
      }
    }
    if (marker != null) {
      final x = (size.width * marker!.clamp(0.0, 1.0)).clamp(1.0, size.width - 1.0);
      canvas.drawLine(Offset(x, -2), Offset(x, h + 5), Paint()..color = Pk.bone..strokeWidth = 1.5);
    }
  }

  @override
  bool shouldRepaint(_SegPainter old) => old.v != v || old.color != color || old.marker != marker;
}

/// Small bordered tag.
class Tag extends StatelessWidget {
  const Tag(this.text, {super.key, this.color = Pk.muted, this.filled = false});
  final String text;
  final Color color;
  final bool filled;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
      decoration: BoxDecoration(
        color: filled ? color : Colors.transparent,
        borderRadius: BorderRadius.circular(Pk.rIn),
        border: Border.all(color: filled ? color : color.withValues(alpha: 0.55)),
      ),
      child: Text(text.toUpperCase(), style: Pk.label(c: filled ? Pk.ink : color, size: 10)),
    );
  }
}

/// Selectable chip used for filters and quick prompts.
class PChip extends StatelessWidget {
  const PChip({super.key, required this.label, this.selected = false, this.onTap, this.icon});
  final String label;
  final bool selected;
  final VoidCallback? onTap;
  final IconData? icon;

  @override
  Widget build(BuildContext context) {
    return Pressable(
      onTap: onTap,
      semantics: label,
      child: Center(
        widthFactor: 1,
        child: AnimatedContainer(
          duration: Pk.fast,
          height: 34,
          padding: const EdgeInsets.symmetric(horizontal: 12),
          decoration: BoxDecoration(
            color: selected ? Pk.bone : Colors.transparent,
            borderRadius: BorderRadius.circular(Pk.rSm),
            border: Border.all(color: selected ? Pk.bone : Pk.lineStrong),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (icon != null) ...[Icon(icon, size: 14, color: selected ? Pk.ink : Pk.muted), const SizedBox(width: 6)],
              Text(label, style: Pk.text(13.5, w: FontWeight.w500, c: selected ? Pk.ink : Pk.bone)),
            ],
          ),
        ),
      ),
    );
  }
}

/// Emoji in a square tile, so mixed emoji widths line up.
class EmojiTile extends StatelessWidget {
  const EmojiTile(this.emoji, {super.key, this.size = 36});
  final String emoji;
  final double size;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      alignment: Alignment.center,
      decoration: BoxDecoration(color: Pk.raised, borderRadius: BorderRadius.circular(Pk.rSm), border: Border.all(color: Pk.line)),
      child: Text(emoji.isEmpty ? '•' : emoji, style: TextStyle(fontSize: size * 0.46, height: 1.1)),
    );
  }
}

/// Initials in a square: people in groups.
class InitialTile extends StatelessWidget {
  const InitialTile(this.name, {super.key, this.size = 30, this.highlight = false});
  final String name;
  final double size;
  final bool highlight;

  @override
  Widget build(BuildContext context) {
    final parts = name.trim().split(RegExp(r'\s+')).where((p) => p.isNotEmpty).toList();
    final initials = parts.isEmpty ? '?' : (parts.length == 1 ? parts[0].characters.first : parts[0].characters.first + parts.last.characters.first);
    return Container(
      width: size,
      height: size,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        color: highlight ? Pk.lime : Pk.raised,
        borderRadius: BorderRadius.circular(Pk.rSm),
        border: Border.all(color: highlight ? Pk.lime : Pk.lineStrong),
      ),
      child: Text(initials.toUpperCase(), style: Pk.label(c: highlight ? Pk.limeInk : Pk.bone, size: size * 0.36)),
    );
  }
}

/// Enter animation: fade and rise a little. Stagger by index so a screen builds piece by piece.
class Rise extends StatefulWidget {
  const Rise({super.key, required this.child, this.index = 0, this.step = 70});
  final Widget child;
  final int index;
  final int step;

  @override
  State<Rise> createState() => _RiseState();
}

class _RiseState extends State<Rise> with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(vsync: this, duration: const Duration(milliseconds: 420));

  @override
  void initState() {
    super.initState();
    Future.delayed(Duration(milliseconds: widget.step * widget.index.clamp(0, 10)), () {
      if (mounted) _c.forward();
    });
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (MediaQuery.of(context).disableAnimations) return widget.child;
    final curved = CurvedAnimation(parent: _c, curve: Pk.ease);
    return FadeTransition(
      opacity: curved,
      child: SlideTransition(position: Tween(begin: const Offset(0, 0.06), end: Offset.zero).animate(curved), child: widget.child),
    );
  }
}

/// Loading placeholder with a slow pulse (no shimmer sweep: calmer).
class Skeleton extends StatefulWidget {
  const Skeleton({super.key, this.height = 80});
  final double height;

  @override
  State<Skeleton> createState() => _SkeletonState();
}

class _SkeletonState extends State<Skeleton> with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(vsync: this, duration: const Duration(milliseconds: 1100))..repeat(reverse: true);

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return FadeTransition(
      opacity: Tween(begin: 0.45, end: 1.0).animate(_c),
      child: Container(
        height: widget.height,
        decoration: BoxDecoration(color: Pk.surface, borderRadius: BorderRadius.circular(Pk.r), border: Border.all(color: Pk.line)),
      ),
    );
  }
}

/// Empty and error states share one shape: a line of what happened and one thing to do.
class StateNote extends StatelessWidget {
  const StateNote({super.key, required this.title, this.body, this.action, this.onAction, this.icon = Icons.inbox_outlined, this.color = Pk.muted});
  final String title;
  final String? body;
  final String? action;
  final VoidCallback? onAction;
  final IconData icon;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 28, horizontal: 8),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 26, color: color),
          const SizedBox(height: 12),
          Text(title, textAlign: TextAlign.center, style: Pk.text(16, w: FontWeight.w600)),
          if (body != null) ...[
            const SizedBox(height: 6),
            Text(body!, textAlign: TextAlign.center, style: Pk.text(14, c: Pk.muted, h: 1.4)),
          ],
          if (action != null) ...[const SizedBox(height: 16), GhostButton(label: action!, onTap: onAction, dense: true)],
        ],
      ),
    );
  }
}

/// Bottom sheet with the house style: grab bar, title, scrollable body.
Future<T?> showPocketSheet<T>(BuildContext context, {required String title, required Widget Function(BuildContext) builder, bool tall = false}) {
  return showModalBottomSheet<T>(
    context: context,
    isScrollControlled: true,
    useSafeArea: true,
    barrierColor: const Color(0xB3000000),
    constraints: const BoxConstraints(maxWidth: 520),
    builder: (ctx) => Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.of(ctx).viewInsets.bottom),
      child: ConstrainedBox(
        constraints: BoxConstraints(maxHeight: MediaQuery.of(ctx).size.height * (tall ? 0.9 : 0.78)),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const SizedBox(height: 10),
            Center(child: Container(width: 36, height: 3, color: Pk.lineStrong)),
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 16, 12, 4),
              child: Row(
                children: [
                  Expanded(child: Text(title, style: Pk.text(20, w: FontWeight.w600, h: 1.2))),
                  IconButton(onPressed: () => Navigator.of(ctx).pop(), icon: const Icon(Icons.close, size: 20, color: Pk.muted), tooltip: MaterialLocalizations.of(ctx).closeButtonLabel),
                ],
              ),
            ),
            Flexible(child: SingleChildScrollView(padding: const EdgeInsets.fromLTRB(20, 8, 20, 24), child: builder(ctx))),
          ],
        ),
      ),
    ),
  );
}

void toast(BuildContext context, String message) {
  ScaffoldMessenger.of(context)
    ..hideCurrentSnackBar()
    ..showSnackBar(SnackBar(content: Text(message), duration: const Duration(seconds: 3), width: 360));
}
