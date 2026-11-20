import 'package:material_ui/material_ui.dart';

import '../../../core/json.dart';
import '../widgets.dart';

/// One Home entry after rendering: the widget plus what the edit sheet needs to know about it.
class HomeEntry {
  const HomeEntry({required this.type, required this.variant, required this.params, required this.widget, this.reason});
  final String type;
  final String variant;
  final Json params;
  final Widget widget;
  final String? reason;

  Json toSpec() => {'type': type, 'variant': variant, 'params': params};
}

/// Builds one catalog widget, or null for a type outside the catalog. The app passes
/// [buildCatalogWidget]; tests pass a stand-in that needs no app state.
typedef CatalogWidgetBuilder = Widget? Function(String type, {required Json params, required String variant, required int index});

/// Direct renderer: LayoutSpec -> the catalog widgets, in order.
///
/// It is the fallback that keeps Home alive if the A2UI package breaks. It enforces the two
/// rules the phone must never get wrong whatever it is sent: only catalog widgets are drawn,
/// and Safe-to-spend is first.
List<HomeEntry> renderDirect(Json spec, {CatalogWidgetBuilder build = buildCatalogWidget}) {
  final reasons = {for (final r in spec.l('reasons')) r.i('widget_index', -1): r.s('text')};
  final entries = <HomeEntry>[];
  final raw = spec.l('widgets');
  final seenHero = raw.any((w) => w.s('type') == 'safe_to_spend');
  final ordered = [
    if (!seenHero) <String, dynamic>{'type': 'safe_to_spend', 'variant': 'hero', 'params': <String, dynamic>{}},
    ...raw.where((w) => w.s('type') == 'safe_to_spend').take(1),
    ...raw.where((w) => w.s('type') != 'safe_to_spend'),
  ];
  for (final w in ordered) {
    final type = w.s('type');
    final params = w.m('params');
    final variant = w.s('variant', 'default');
    final built = build(type, params: params, variant: variant, index: entries.length);
    if (built == null) continue; // unknown type: rejected
    final originalIndex = raw.indexOf(w);
    entries.add(HomeEntry(type: type, variant: variant, params: params, widget: built, reason: reasons[originalIndex]));
  }
  return entries;
}
