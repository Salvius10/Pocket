import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:pocket/core/format.dart';

import 'fixtures.dart';

/// The same 100 cases the Python tests check (data/fixtures/money_format.json), so money looks
/// identical whichever side formats it.
void main() {
  final file = File(fixturePath('money_format.json'));
  final cases = (jsonDecode(file.readAsStringSync()) as List).cast<Map<String, dynamic>>();

  test('fixture file has 100 cases', () => expect(cases.length, 100));

  test('display, exact and spoken match the shared fixtures', () {
    for (final c in cases) {
      final paise = c['paise'] as int;
      expect(displayPaise(paise), c['display'], reason: 'display($paise)');
      expect(exactPaise(paise), c['exact'], reason: 'exact($paise)');
      final spoken = (c['spoken'] as Map).cast<String, dynamic>();
      for (final lang in spoken.keys) {
        expect(spokenPaise(paise, lang), spoken[lang], reason: 'spoken($paise, $lang)');
      }
    }
  });

  test('hand-checked anchors', () {
    expect(displayPaise(12345650), '₹1,23,457');
    expect(exactPaise(12345650), '₹1,23,456.50');
    expect(spokenPaise(843900), '₹8,400');
    expect(spokenPaise(12000000), '₹1.2 lakh');
    expect(spokenPaise(1050000000, 'ta'), '₹1.05 கோடி');
    expect(groupIndian(12345678), '1,23,45,678');
  });

  test('typed rupees become paise without floats', () {
    expect(rupeesToPaise('1,250.50'), 125050);
    expect(rupeesToPaise('3000'), 300000);
    expect(rupeesToPaise('0.1'), 10);
    expect(rupeesToPaise('12.345'), isNull);
    expect(rupeesToPaise('abc'), isNull);
    expect(rupeesToPaise(''), isNull);
  });
}
