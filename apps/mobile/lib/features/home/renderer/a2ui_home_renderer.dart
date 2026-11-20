import 'dart:convert';

import 'package:a2ui_core/a2ui_core.dart' as a2ui;
import 'package:a2ui_flutter/a2ui_flutter.dart' as a2f;
import 'package:json_schema_builder/json_schema_builder.dart' show Schema;
import 'package:material_ui/material_ui.dart';

import '../../../core/json.dart';
import '../../../core/theme.dart';
import '../../../core/ui.dart';
import '../widgets.dart';
import 'a2ui_contract.dart';
import 'direct_renderer.dart';

/// Home renderer entry point, and the one adapter file for the A2UI packages (CLAUDE.md):
/// `a2ui_core` 0.8.0 and `a2ui_flutter` 0.4.0, A2UI protocol v1.0.
///
/// core-api stores each layout twice: as a LayoutSpec and as A2UI v1.0 messages built from it
/// by code (`createSurface` + `updateComponents`, root `PocketHomeColumn`, one component per
/// catalog widget, camelCase props, never a money value).
///
/// [HomeSurface] draws Home with `a2ui_flutter`'s `A2uiSurface` from those messages. Each
/// component's builder returns the same catalog widget the direct renderer uses, and the widgets
/// read their numbers from the local cache, so A2UI carries layout only.
///
/// The direct renderer stays as the fallback. It takes over when the messages are missing, come
/// from another protocol or catalog version, name anything outside the catalog, do not start
/// with Safe-to-spend, or when the package reports any error. So a package break or a version
/// skew between backend and app changes nothing the user sees.

// ---------- which layouts A2UI may draw ----------

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

/// [checkA2ui], plus the two rules the phone enforces whatever it is sent: only catalog widgets
/// are drawn, and Safe-to-spend is first. A layout that breaks either goes to the direct
/// renderer, which repairs it.
({bool ok, String reason}) checkA2uiSurface(Json home) {
  final check = checkA2ui(home);
  if (!check.ok) return check;
  if (home.l('a2ui').length != 2) return (ok: false, reason: 'expected one createSurface and one updateComponents');
  final update = home.l('a2ui').where((m) => m['updateComponents'] is Map).last;
  final components = {for (final c in update.m('updateComponents').l('components')) c.s('id'): c};
  final children = components['root']!.strings('children');
  if (children.isEmpty) return (ok: false, reason: 'no widgets');
  for (final id in children) {
    final name = components[id]?.s('component');
    if (!A2uiContract.componentTypes.containsKey(name)) return (ok: false, reason: 'component "$name" is not in the Pocket catalog');
  }
  if (components.length != children.length + 1) return (ok: false, reason: 'components that are not on the Home column');
  if (components[children.first]!.s('component') != 'SafeToSpend') return (ok: false, reason: 'Safe-to-spend is not first');
  return (ok: true, reason: '');
}

// ---------- what Home lists (for the edit and "why" sheets, and the fallback) ----------

/// The Home entries in order. Reads the A2UI messages when this build can; otherwise the
/// LayoutSpec that ships in the same response.
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

// ---------- the Pocket Home catalog for the A2UI packages ----------

Schema _widgetSchema(String component) => Schema.fromMap({
      'type': 'object',
      'properties': {
        'variant': {'type': 'string', 'enum': ['default', 'hero', 'compact']},
        'reason': {'type': 'string'},
        for (final e in A2uiContract.componentParams[component]!.entries) e.key: {'type': e.value},
      },
    });

Schema _rootSchema() => Schema.fromMap({
      'type': 'object',
      'properties': {
        'children': {r'$ref': r'common_types.json#/$defs/ChildList'},
        'summary': {'type': 'string'},
      },
      'required': ['children'],
    });

/// The catalog as `a2ui_core` alone understands it (names and schemas, nothing to draw).
/// The contract test feeds the backend's messages through it.
a2ui.Catalog<a2ui.ComponentApi, a2ui.FunctionImplementation> pocketHomeCatalog() {
  return a2ui.Catalog<a2ui.ComponentApi, a2ui.FunctionImplementation>(
    id: A2uiContract.catalogId,
    title: 'Pocket Home',
    protocolVersion: a2ui.A2uiProtocolVersion.v1_0,
    components: [
      a2ui.ComponentApi(name: A2uiContract.rootComponent, schema: _rootSchema()),
      for (final name in A2uiContract.componentTypes.keys) a2ui.ComponentApi(name: name, schema: _widgetSchema(name)),
    ],
  );
}

/// The catalog with builders: what `a2ui_flutter` draws for each component.
a2f.CatalogImplementation pocketHomeWidgets(CatalogWidgetBuilder build) {
  return a2f.CatalogImplementation(
    id: A2uiContract.catalogId,
    title: 'Pocket Home',
    protocolVersion: a2ui.A2uiProtocolVersion.v1_0,
    components: [
      a2f.ComponentImplementation(
        name: A2uiContract.rootComponent,
        schema: _rootSchema(),
        builder: (context, node, props, buildChild) {
          final children = props.children('children');
          return Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              for (final (i, child) in children.indexed)
                KeyedSubtree(
                  key: a2f.NodeKey(child.instanceId),
                  child: Padding(
                    padding: const EdgeInsets.only(bottom: Pk.gap),
                    child: Rise(index: i, child: _Slot(index: i, child: buildChild(child))),
                  ),
                ),
            ],
          );
        },
      ),
      for (final name in A2uiContract.componentTypes.keys)
        a2f.ComponentImplementation(
          name: name,
          schema: _widgetSchema(name),
          builder: (context, node, props, buildChild) {
            final params = <String, dynamic>{};
            for (final key in A2uiContract.componentParams[name]!.keys) {
              final value = props.value(key);
              if (value != null) params[_snake(key)] = value is double && value == value.roundToDouble() ? value.toInt() : value;
            }
            final variant = props.string('variant') ?? 'default';
            return build(A2uiContract.componentTypes[name]!, params: params, variant: variant, index: _Slot.of(context)) ?? const SizedBox.shrink();
          },
        ),
    ],
  );
}

/// A widget's position on Home (its section number), handed down by the column.
class _Slot extends InheritedWidget {
  const _Slot({required this.index, required super.child});
  final int index;

  static int of(BuildContext context) => context.dependOnInheritedWidgetOfExactType<_Slot>()?.index ?? 0;

  @override
  bool updateShouldNotify(_Slot oldWidget) => oldWidget.index != index;
}

// ---------- the widget Home mounts ----------

/// Home's widgets, drawn by `a2ui_flutter` from the stored A2UI messages, with the direct
/// renderer underneath as the fallback.
class HomeSurface extends StatefulWidget {
  const HomeSurface({super.key, required this.home, this.build = buildCatalogWidget});

  /// The stored layout: `{version, spec, a2ui}`.
  final Json home;
  final CatalogWidgetBuilder build;

  @override
  State<HomeSurface> createState() => HomeSurfaceState();
}

class HomeSurfaceState extends State<HomeSurface> {
  a2ui.MessageProcessor<a2f.ComponentImplementation>? _processor;
  a2ui.SurfaceModel<a2f.ComponentImplementation>? _surface;
  String _signature = '';

  /// True when `a2ui_flutter` is drawing this layout; false when the direct renderer is.
  bool get usesA2ui => _surface != null;

  /// Why the direct renderer is drawing, when it is.
  String fallbackReason = '';

  static String _sign(Json home) => '${home['version']}|${jsonEncode(home['a2ui'])}';

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void didUpdateWidget(HomeSurface oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (_sign(widget.home) != _signature || !identical(oldWidget.build, widget.build)) _load();
  }

  void _load() {
    _processor?.dispose();
    _processor = null;
    _surface = null;
    _signature = _sign(widget.home);
    final check = checkA2uiSurface(widget.home);
    if (!check.ok) {
      fallbackReason = check.reason;
      return;
    }
    a2ui.MessageProcessor<a2f.ComponentImplementation>? processor;
    try {
      processor = a2ui.MessageProcessor<a2f.ComponentImplementation>(
        catalogs: [pocketHomeWidgets(widget.build)],
        defaultVersion: a2ui.A2uiProtocolVersion.v1_0,
      );
      final errors = processor.processMessagesWithErrors(widget.home.l('a2ui'));
      final surface = processor.model.getSurface(A2uiContract.surfaceId);
      if (errors.isEmpty && surface != null) {
        _processor = processor;
        _surface = surface;
        fallbackReason = '';
        return;
      }
      fallbackReason = errors.isEmpty ? 'the package created no surface' : 'the package reported: ${errors.first.error}';
    } catch (error) {
      fallbackReason = 'the package threw: $error';
    }
    processor?.dispose();
    debugPrint('Home: A2UI not used ($fallbackReason); drawing from the LayoutSpec');
  }

  @override
  void dispose() {
    _processor?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final surface = _surface;
    if (surface != null) return a2f.A2uiSurface(surface: surface);
    final entries = renderDirect(_fallbackSpec(), build: widget.build);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        for (final (i, e) in entries.indexed)
          Padding(
            key: ValueKey('${widget.home['version']}-${e.type}-$i'),
            padding: const EdgeInsets.only(bottom: Pk.gap),
            child: Rise(index: i, child: e.widget),
          ),
      ],
    );
  }

  Json _fallbackSpec() {
    final spec = widget.home.m('spec');
    if (spec.l('widgets').isNotEmpty) return spec;
    try {
      if (checkA2ui(widget.home).ok) return _specFromA2ui(widget.home) ?? spec;
    } catch (_) {
      // nothing usable in the messages either: the direct renderer still shows Safe-to-spend
    }
    return spec;
  }
}
