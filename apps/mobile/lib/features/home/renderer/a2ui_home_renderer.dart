import 'package:flutter/foundation.dart' show debugPrint;

import '../../../core/json.dart';
import 'a2ui_contract.dart';
import 'direct_renderer.dart';

/// Home renderer entry point, and the one adapter file for A2UI (CLAUDE.md).
///
/// core-api stores each layout twice: as a LayoutSpec and as A2UI v1.0 messages built from it
/// by code (`createSurface` + `updateComponents`, root `PocketHomeColumn`, one component per
/// catalog widget, camelCase props, never a money value).
///
/// [renderHome] draws from the A2UI messages only when [checkA2ui] says the agent side and this
/// build agree on protocol version, catalog and root component. On any mismatch, or anything
/// malformed, it falls back to the direct renderer on the LayoutSpec, so a version skew between
/// backend and app changes nothing the user sees. Both paths use the same catalog widgets.
List<HomeEntry> renderHome(Json home) {
  try {
    final check = checkA2ui(home);
    if (check.ok) {
      final fromA2ui = _specFromA2ui(home);
      if (fromA2ui != null) return renderDirect(fromA2ui);
    } else if (home.l('a2ui').isNotEmpty) {
      debugPrint('Home: A2UI not used (${check.reason}); drawing from the LayoutSpec');
    }
  } catch (_) {
    // fall through: a package or payload problem must never take Home down
  }
  return renderDirect(home.m('spec'));
}

/// Whether this build can read the layout's A2UI messages, and if not, why.
({bool ok, String reason}) checkA2ui(Json home) {
  final messages = home.l('a2ui');
  if (messages.isEmpty) return (ok: false, reason: 'no A2UI messages');
  for (final m in messages) {
    final version = m.s('version');
    if (!A2uiContract.supportedProtocolVersions.contains(version)) {
      return (ok: false, reason: 'protocol version "$version" is not one of ${A2uiContract.supportedProtocolVersions}');
    }
  }
  final create = messages.where((m) => m['createSurface'] is Map).firstOrNull;
  if (create == null) return (ok: false, reason: 'no createSurface message');
  final catalog = create.m('createSurface').s('catalogId');
  if (catalog != A2uiContract.catalogId) {
    return (ok: false, reason: 'catalog "$catalog" is not ${A2uiContract.catalogId}');
  }
  final surface = create.m('createSurface').s('surfaceId');
  final update = messages.where((m) => m['updateComponents'] is Map).lastOrNull;
  if (update == null || update.m('updateComponents').s('surfaceId') != surface) {
    return (ok: false, reason: 'no updateComponents for surface "$surface"');
  }
  final root = update.m('updateComponents').l('components').where((c) => c.s('id') == 'root').firstOrNull;
  if (root == null || root.s('component') != A2uiContract.rootComponent) {
    return (ok: false, reason: 'root component is not ${A2uiContract.rootComponent}');
  }
  return (ok: true, reason: '');
}

String _snake(String camel) => camel.replaceAllMapped(RegExp('[A-Z]'), (m) => '_${m[0]!.toLowerCase()}');

Json? _specFromA2ui(Json home) {
  final update = home.l('a2ui').where((m) => m['updateComponents'] is Map).last;
  final components = {for (final c in update.m('updateComponents').l('components')) c.s('id'): c};
  final root = components['root']!;
  final widgets = <Json>[];
  final reasons = <Json>[];
  for (final id in root.strings('children')) {
    final c = components[id];
    final type = c == null ? null : A2uiContract.componentTypes[c.s('component')];
    if (c == null || type == null) continue; // not in the Pocket catalog: rejected
    final params = <String, dynamic>{
      for (final e in c.entries)
        if (!const {'id', 'component', 'variant', 'reason'}.contains(e.key)) _snake(e.key): e.value,
    };
    if (c.s('reason').isNotEmpty) reasons.add({'widget_index': widgets.length, 'text': c.s('reason')});
    widgets.add({'type': type, 'variant': c.s('variant', 'default'), 'params': params});
  }
  if (widgets.isEmpty) return null;
  return {'widgets': widgets, 'reasons': reasons, 'summary': root.s('summary')};
}
