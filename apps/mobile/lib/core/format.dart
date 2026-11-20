/// Money formatting on the phone. Same rules as `pocket_common.money` in Python and tested
/// against the same fixture file. The app only formats what the user types (previews) and
/// parses typed rupees into paise; every total it shows comes from the API.
library;

const _rupee = '₹';

int divHalfUp(int n, int d) {
  final sign = n < 0 ? -1 : 1;
  return sign * ((n.abs() * 2 + d) ~/ (2 * d));
}

/// 12345678 -> "1,23,45,678"
String groupIndian(int n) {
  final s = n.abs().toString();
  if (s.length <= 3) return s;
  var head = s.substring(0, s.length - 3);
  final tail = s.substring(s.length - 3);
  final parts = <String>[];
  while (head.length > 2) {
    parts.insert(0, head.substring(head.length - 2));
    head = head.substring(0, head.length - 2);
  }
  if (head.isNotEmpty) parts.insert(0, head);
  return '${parts.join(',')},$tail';
}

/// Whole rupees, half-up: 12345650 -> "₹1,23,457".
String displayPaise(int paise) {
  final rupees = divHalfUp(paise.abs(), 100);
  final sign = paise < 0 && rupees != 0 ? '-' : '';
  return '$sign$_rupee${groupIndian(rupees)}';
}

/// Rupees and paise, two decimals: 12345650 -> "₹1,23,456.50".
String exactPaise(int paise) {
  final a = paise.abs();
  return '${paise < 0 ? '-' : ''}$_rupee${groupIndian(a ~/ 100)}.${(a % 100).toString().padLeft(2, '0')}';
}

String _trim(int hundredths) {
  final whole = hundredths ~/ 100, frac = hundredths % 100;
  if (frac == 0) return '$whole';
  if (frac % 10 == 0) return '$whole.${frac ~/ 10}';
  return '$whole.${frac.toString().padLeft(2, '0')}';
}

const _units = {
  'en': ('lakh', 'crore'),
  'hi': ('लाख', 'करोड़'),
  'ta': ('லட்சம்', 'கோடி'),
};

/// Ready-to-speak amount: exact to the rupee under ₹1,000, nearest ₹100 under ₹1 lakh, then lakh / crore.
String spokenPaise(int paise, [String lang = 'en']) {
  final (lakh, crore) = _units[lang] ?? _units['en']!;
  const lakhPaise = 10000000, crorePaise = 1000000000;
  var a = paise.abs();
  final sign = paise < 0 ? '-' : '';
  final rupees = divHalfUp(a, 100);
  if (rupees < 1000) return '${rupees == 0 ? '' : sign}$_rupee$rupees';
  if (a < lakhPaise) {
    final rounded = divHalfUp(a, 10000) * 100;
    if (rounded < 100000) return '$sign$_rupee${groupIndian(rounded)}';
    a = rounded * 100;
  }
  if (a < crorePaise) {
    final h = divHalfUp(a, lakhPaise ~/ 100);
    if (h < 10000) return '$sign$_rupee${_trim(h)} $lakh';
    a = h * (lakhPaise ~/ 100);
  }
  return '$sign$_rupee${_trim(divHalfUp(a, crorePaise ~/ 100))} $crore';
}

/// "1,250.50" typed by the user -> 125050 paise. Null when it is not an amount.
int? rupeesToPaise(String input) {
  final cleaned = input.replaceAll(',', '').replaceAll(_rupee, '').trim();
  if (!RegExp(r'^\d{1,9}(\.\d{0,2})?$').hasMatch(cleaned)) return null;
  final parts = cleaned.split('.');
  final frac = parts.length > 1 ? parts[1].padRight(2, '0') : '00';
  return int.parse(parts[0]) * 100 + int.parse(frac.isEmpty ? '0' : frac);
}
