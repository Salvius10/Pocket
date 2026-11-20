import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:material_ui/material_ui.dart';
import 'package:pocket/core/json.dart';
import 'package:pocket/features/home/renderer/a2ui_contract.dart';
import 'package:pocket/features/home/renderer/a2ui_home_renderer.dart';

import 'fixtures.dart';

/// Home through both renderers: `a2ui_flutter`'s surface (from the backend's A2UI messages) and
/// the direct renderer (from the LayoutSpec). A stand-in replaces the real catalog widgets, so
/// what is compared is exactly what each renderer decides: which widget, in which slot, with
/// which variant and params.
Widget? standIn(String type, {required Json params, required String variant, required int index}) {
  if (!A2uiContract.componentTypes.containsValue(type)) return null;
  final sorted = {for (final k in params.keys.toList()..sort()) k: params[k]};
  return Text('$index|$type|$variant|${jsonEncode(sorted)}');
}

Future<(List<String>, bool, String)> draw(WidgetTester tester, Json home) async {
  await tester.pumpWidget(const SizedBox.shrink()); // a fresh surface each time
  await tester.pumpWidget(MaterialApp(home: Scaffold(body: SingleChildScrollView(child: HomeSurface(home: home, build: standIn)))));
  await tester.pumpAndSettle();
  expect(tester.takeException(), isNull);
  final state = tester.state<HomeSurfaceState>(find.byType(HomeSurface));
  final lines = [for (final t in tester.widgetList<Text>(find.byType(Text))) t.data!];
  return (lines, state.usesA2ui, state.fallbackReason);
}

List<dynamic> copy(List<dynamic> messages) => jsonDecode(jsonEncode(messages)) as List;

void main() {
  final contract = Map<String, dynamic>.from(jsonDecode(File(fixturePath('a2ui_home.json')).readAsStringSync()) as Map);
  final layouts = <String, Json>{
    'every widget type': contract,
    for (final row in contract.l('ideal_layouts')) 'default layout: ${row.s('persona_id')}': row,
  };

  for (final MapEntry(key: name, value: layout) in layouts.entries) {
    testWidgets('$name renders identically through both renderers', (tester) async {
      final spec = layout.m('spec');
      final (viaA2ui, usedA2ui, reason) = await draw(tester, {'version': 1, 'spec': spec, 'a2ui': layout['messages']});
      expect(usedA2ui, isTrue, reason: reason);
      final (direct, usedA2uiForDirect, _) = await draw(tester, {'version': 1, 'spec': spec, 'a2ui': <dynamic>[]});
      expect(usedA2uiForDirect, isFalse);

      expect(viaA2ui, direct);
      expect(viaA2ui.length, spec.l('widgets').length);
      expect(viaA2ui.first, startsWith('0|safe_to_spend|'));
    });
  }

  testWidgets('a2ui_flutter draws from the messages alone', (tester) async {
    final (lines, usedA2ui, _) = await draw(tester, {'version': 1, 'spec': <String, dynamic>{}, 'a2ui': contract['messages']});
    expect(usedA2ui, isTrue);
    expect(lines.first, '0|safe_to_spend|hero|{}');
    expect(lines, contains('1|bills_emis|compact|{"window_days":14}'));
  });

  group('the direct renderer takes over', () {
    final spec = contract.m('spec');
    Future<void> expectFallback(WidgetTester tester, List<dynamic> messages, String why) async {
      final (direct, _, _) = await draw(tester, {'version': 1, 'spec': spec, 'a2ui': <dynamic>[]});
      final (lines, usedA2ui, reason) = await draw(tester, {'version': 1, 'spec': spec, 'a2ui': messages});
      expect(usedA2ui, isFalse);
      expect(reason, contains(why));
      expect(lines, direct);
      expect(lines.first, startsWith('0|safe_to_spend|'));
    }

    testWidgets('for a newer protocol version', (tester) async {
      final messages = jsonDecode(jsonEncode(contract['messages']).replaceAll('"version":"1.0"', '"version":"2.0"')) as List;
      await expectFallback(tester, messages, 'protocol version');
    });

    testWidgets('for another catalog', (tester) async {
      final messages = jsonDecode(jsonEncode(contract['messages']).replaceAll('/home/v1', '/home/v2')) as List;
      await expectFallback(tester, messages, 'catalog');
    });

    testWidgets('for a component outside the catalog, which is never drawn', (tester) async {
      final messages = copy(contract.l('messages'));
      final components = (messages[1] as Map)['updateComponents']['components'] as List;
      components.add({'id': 'x', 'component': 'CryptoTicker'});
      ((components.first as Map)['children'] as List).add('x');
      await expectFallback(tester, messages, 'not in the Pocket catalog');
      expect(find.textContaining('CryptoTicker'), findsNothing);
    });

    testWidgets('when Safe-to-spend is not first, and puts it first', (tester) async {
      final messages = copy(contract.l('messages'));
      final children = ((messages[1] as Map)['updateComponents']['components'] as List).first['children'] as List;
      children.add(children.removeAt(0)); // move Safe-to-spend to the end
      await expectFallback(tester, messages, 'Safe-to-spend is not first');
    });

    testWidgets('for a stray component that is not on the Home column', (tester) async {
      final messages = copy(contract.l('messages'));
      ((messages[1] as Map)['updateComponents']['components'] as List).add({'id': 'loose', 'component': 'Pockets'});
      await expectFallback(tester, messages, 'not on the Home column');
    });
  });

  testWidgets('a new layout version redraws Home', (tester) async {
    final first = contract.l('ideal_layouts').first;
    final second = contract.l('ideal_layouts').last;
    Widget app(Json row, int version) => MaterialApp(
          home: Scaffold(body: SingleChildScrollView(child: HomeSurface(home: {'version': version, 'spec': row['spec'], 'a2ui': row['messages']}, build: standIn))),
        );
    await tester.pumpWidget(app(first, 1));
    await tester.pumpAndSettle();
    final before = [for (final t in tester.widgetList<Text>(find.byType(Text))) t.data!];
    await tester.pumpWidget(app(second, 2));
    await tester.pumpAndSettle();
    final after = [for (final t in tester.widgetList<Text>(find.byType(Text))) t.data!];
    expect(tester.takeException(), isNull);
    expect(after, isNot(before));
    expect(after.length, second.m('spec').l('widgets').length);
    expect(tester.state<HomeSurfaceState>(find.byType(HomeSurface)).usesA2ui, isTrue);
  });
}
