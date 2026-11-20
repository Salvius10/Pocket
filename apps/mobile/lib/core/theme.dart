import 'package:material_ui/material_ui.dart';

/// Pocket's look: dark, a little brutalist, calm.
///
/// One accent (lime) on warm near-black. Numbers are set in a mono face with
/// tabular figures so amounts never jitter. Corners are tight, borders are
/// real 1px lines, and the dashed "stitch" line (from the mascot's pocket)
/// is the recurring motif.
abstract final class Pk {
  // Surfaces
  static const ink = Color(0xFF0C0D0A);
  static const surface = Color(0xFF141511);
  static const raised = Color(0xFF1C1E18);
  static const line = Color(0xFF2B2D25);
  static const lineStrong = Color(0xFF45483B);

  // Text
  static const bone = Color(0xFFEDE9DD);
  static const muted = Color(0xFF9D9B8F);
  static const faint = Color(0xFF6B6A60);

  // Signals
  static const lime = Color(0xFFC8F169);
  static const limeDeep = Color(0xFF8FB23F);
  static const limeInk = Color(0xFF1A2108);
  static const coral = Color(0xFFF2795B);
  static const amber = Color(0xFFEFC15A);
  static const sage = Color(0xFF7FB7A3);
  static const dusk = Color(0xFF8DA9C4);
  static const clay = Color(0xFFC4A484);

  /// Calm, distinguishable series colours for charts (first = biggest slice).
  static const series = [lime, bone, sage, amber, dusk, coral, clay, faint];

  // Shape
  static const r = 6.0; // cards
  static const rSm = 4.0; // buttons, chips
  static const rIn = 2.0; // things nested inside a padded card (concentric)
  static const gap = 12.0;
  static const pad = 16.0;

  static const sans = 'Bricolage';
  static const mono = 'PlexMono';

  static const tabular = [FontFeature.tabularFigures()];

  /// Body and headings. Bricolage is a variable font: `opsz` follows size.
  static TextStyle text(double size, {FontWeight w = FontWeight.w400, Color c = bone, double? h, double ls = 0}) {
    return TextStyle(
      fontFamily: sans,
      fontSize: size,
      fontWeight: w,
      color: c,
      height: h,
      letterSpacing: ls,
      fontVariations: [FontVariation('opsz', size.clamp(12, 96)), FontVariation('wght', w.value.toDouble())],
    );
  }

  /// Amounts and data. Always tabular.
  static TextStyle num(double size, {FontWeight w = FontWeight.w500, Color c = bone, double? h, double ls = 0}) {
    return TextStyle(fontFamily: mono, fontSize: size, fontWeight: w, color: c, height: h, letterSpacing: ls, fontFeatures: tabular);
  }

  /// Small uppercase mono label: "02 · POCKETS".
  static TextStyle label({Color c = muted, double size = 11}) {
    return TextStyle(fontFamily: mono, fontSize: size, fontWeight: FontWeight.w500, color: c, letterSpacing: 1.2, height: 1.2);
  }

  static Color statusColor(String? status) => switch (status) {
        'over' || 'behind' || 'owes' => coral,
        'watch' || 'tight' => amber,
        'reached' || 'owed' => lime,
        _ => bone,
      };

  static const fast = Duration(milliseconds: 140);
  static const med = Duration(milliseconds: 260);
  static const slow = Duration(milliseconds: 520);
  static const ease = Cubic(0.22, 1, 0.36, 1); // ease-out-quint: quick start, soft landing
}

ThemeData pocketTheme() {
  final base = ThemeData(brightness: Brightness.dark, useMaterial3: true, fontFamily: Pk.sans);
  return base.copyWith(
    scaffoldBackgroundColor: Pk.ink,
    canvasColor: Pk.ink,
    colorScheme: const ColorScheme.dark(
      primary: Pk.lime,
      onPrimary: Pk.limeInk,
      secondary: Pk.bone,
      onSecondary: Pk.ink,
      surface: Pk.surface,
      onSurface: Pk.bone,
      error: Pk.coral,
      onError: Pk.ink,
      outline: Pk.line,
    ),
    splashFactory: NoSplash.splashFactory,
    highlightColor: Colors.transparent,
    hoverColor: Colors.transparent,
    dividerColor: Pk.line,
    textTheme: base.textTheme.apply(fontFamily: Pk.sans, bodyColor: Pk.bone, displayColor: Pk.bone),
    textSelectionTheme: const TextSelectionThemeData(cursorColor: Pk.lime, selectionColor: Color(0x55C8F169), selectionHandleColor: Pk.lime),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: Pk.surface,
      hintStyle: Pk.text(15, c: Pk.faint),
      labelStyle: Pk.label(),
      contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
      border: const OutlineInputBorder(borderRadius: BorderRadius.all(Radius.circular(Pk.rSm)), borderSide: BorderSide(color: Pk.line)),
      enabledBorder: const OutlineInputBorder(borderRadius: BorderRadius.all(Radius.circular(Pk.rSm)), borderSide: BorderSide(color: Pk.line)),
      focusedBorder: const OutlineInputBorder(borderRadius: BorderRadius.all(Radius.circular(Pk.rSm)), borderSide: BorderSide(color: Pk.lime, width: 1.5)),
    ),
    bottomSheetTheme: const BottomSheetThemeData(
      backgroundColor: Pk.surface,
      surfaceTintColor: Colors.transparent,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(10)), side: BorderSide(color: Pk.lineStrong)),
    ),
    snackBarTheme: SnackBarThemeData(
      backgroundColor: Pk.bone,
      contentTextStyle: Pk.text(14, c: Pk.ink, w: FontWeight.w500),
      behavior: SnackBarBehavior.floating,
      shape: const RoundedRectangleBorder(borderRadius: BorderRadius.all(Radius.circular(Pk.rSm))),
    ),
  );
}
