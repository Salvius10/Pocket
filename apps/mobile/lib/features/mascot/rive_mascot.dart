import 'package:material_ui/material_ui.dart';

import 'mascot.dart';

/// The one place the Rive package is allowed to appear (CLAUDE.md: "Verify, pin, isolate").
///
/// Contract with the designer's file `assets/rive/mascot.riv`, driven by data binding
/// (View Model `MascotVM`), never state-machine inputs:
///
///   mood       enum     idle | listening | thinking | talking | happy | concerned | celebrating | sleepy
///   mouthOpen  number   0..100
///   blink      trigger
///   lookX      number   -1..1
///   lookY      number   -1..1
///
/// The file has not arrived yet (BUILD_PLAN human task H3), so `rive` 0.14.x is not a
/// dependency and this returns null: the app shows the painted `FallbackMascot`, which takes
/// the same [MascotController]. When the file arrives: add `rive: 0.14.11` to pubspec.yaml,
/// read that version's README and example, bind the five properties above here, and nothing
/// outside this file changes.
abstract final class RiveMascot {
  static const assetPath = 'assets/rive/mascot.riv';
  static const available = false;

  static Widget? maybeBuild({required MascotController controller, required double size}) {
    if (!available) return null;
    return null;
  }
}
