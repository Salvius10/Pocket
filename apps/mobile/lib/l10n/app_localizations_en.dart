// ignore: unused_import
import 'package:intl/intl.dart' as intl;

import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for English (`en`).
class LEn extends L {
  LEn([String locale = 'en']) : super(locale);

  @override
  String get appName => 'Pocket';

  @override
  String get tabHome => 'Home';

  @override
  String get tabMoney => 'Money';

  @override
  String get tabMascot => 'Poko';

  @override
  String get tabPlan => 'Plan';

  @override
  String get tabCollab => 'Collab';

  @override
  String get retry => 'Try again';

  @override
  String get cancel => 'Cancel';

  @override
  String get confirm => 'Confirm';

  @override
  String get notNow => 'Not now';

  @override
  String get done => 'Done';

  @override
  String get save => 'Save';

  @override
  String get add => 'Add';

  @override
  String get continueLabel => 'Continue';

  @override
  String get skip => 'Skip';

  @override
  String offlineBanner(String time) {
    return 'Offline. Showing your numbers as of $time.';
  }

  @override
  String asOf(String time) {
    return 'As of $time';
  }

  @override
  String get errorTitle => 'Something went wrong';

  @override
  String get errorBody =>
      'We couldn\'t load this. Check your connection and try again.';

  @override
  String get onbTagline => 'Money that explains itself.';

  @override
  String get onbPickLanguage => 'Choose your language';

  @override
  String get onbLangHint => 'You can change this later in Profile.';

  @override
  String get onbTryDemo => 'Try a demo persona';

  @override
  String get onbDemoNote => 'Demo data only. No real bank is connected.';

  @override
  String get onbVoiceTitle => 'Pick Poko\'s voice';

  @override
  String get voiceWarm => 'Warm';

  @override
  String get voiceBright => 'Bright';

  @override
  String get voiceCalm => 'Calm';

  @override
  String get voiceClear => 'Clear';

  @override
  String get onbTalkTitle => 'Tell Poko about your money';

  @override
  String get onbTalkHint => 'Four quick questions. Type or talk.';

  @override
  String get onbSkipTalk => 'Skip the chat';

  @override
  String get onbPickPersona => 'Pick the profile closest to you';

  @override
  String get onbPersonaNote =>
      'Each one is invented, with a year of realistic money.';

  @override
  String get onbSuggested => 'Closest match';

  @override
  String get onbBuild => 'Build my Home';

  @override
  String get onbBuilding => 'Building your Home';

  @override
  String onbStep(int n, int total) {
    return 'Step $n of $total';
  }

  @override
  String get greetMorning => 'Good morning';

  @override
  String get greetAfternoon => 'Good afternoon';

  @override
  String get greetEvening => 'Good evening';

  @override
  String get safeToSpend => 'Safe to spend today';

  @override
  String get perDay => 'a day';

  @override
  String get leftToday => 'Left today';

  @override
  String get spentToday => 'Spent today';

  @override
  String daysLeft(int n) {
    return '$n days left';
  }

  @override
  String overToday(String amount) {
    return 'Over today\'s amount by $amount';
  }

  @override
  String get nothingLeft => 'Nothing left to spend freely this month';

  @override
  String get stsIncome => 'Income';

  @override
  String get stsCommitted => 'Bills & EMIs';

  @override
  String get stsGoals => 'Goals';

  @override
  String get stsSpent => 'Spent';

  @override
  String get stsFormula =>
      'Income, minus bills and goals, minus what you\'ve spent, shared over the days left.';

  @override
  String get wPockets => 'Pockets';

  @override
  String get wGoals => 'Goals';

  @override
  String get wSpend => 'Where it goes';

  @override
  String get wCashFlow => 'Cash flow';

  @override
  String get wTransactions => 'Recent';

  @override
  String get wBills => 'Bills & EMIs';

  @override
  String get wNetWorth => 'Net worth';

  @override
  String get wInvestments => 'Investments';

  @override
  String get wInsight => 'Noticed';

  @override
  String get wPulse => 'Pulse';

  @override
  String get wGroup => 'Group';

  @override
  String get whyLayout => 'Why this layout?';

  @override
  String get whyLayoutTitle => 'Why your Home looks like this';

  @override
  String get editHome => 'Edit Home';

  @override
  String get editHomeHint => 'Drag to reorder. Safe-to-spend stays on top.';

  @override
  String get resetHome => 'Reset to Poko\'s layout';

  @override
  String get askPokoChange => 'Ask Poko to change it';

  @override
  String get homeSaved => 'Home saved';

  @override
  String ofLimit(String limit) {
    return 'of $limit';
  }

  @override
  String leftLabel(String amount) {
    return '$amount left';
  }

  @override
  String overLabel(String amount) {
    return '$amount over';
  }

  @override
  String get statusOver => 'Over';

  @override
  String get statusWatch => 'Watch';

  @override
  String get statusOk => 'On track';

  @override
  String get statusBehind => 'Behind';

  @override
  String get statusReached => 'Reached';

  @override
  String get statusPaused => 'Paused';

  @override
  String get thisMonth => 'This month';

  @override
  String get income => 'In';

  @override
  String get spend => 'Out';

  @override
  String dueIn(int n) {
    return 'in $n days';
  }

  @override
  String get dueToday => 'today';

  @override
  String get dueTomorrow => 'tomorrow';

  @override
  String get overdue => 'overdue';

  @override
  String get autopay => 'Auto';

  @override
  String get assets => 'You have';

  @override
  String get liabilities => 'You owe';

  @override
  String get weekChange => 'This week';

  @override
  String get viewOnly => 'View only. Pocket never asks you to buy or sell.';

  @override
  String get noInsights => 'Nothing new to flag';

  @override
  String get noInsightsBody => 'Poko is watching. Patterns will show up here.';

  @override
  String get forYou => 'For you';

  @override
  String youOwe(String amount) {
    return 'You owe $amount';
  }

  @override
  String youAreOwed(String amount) {
    return 'You are owed $amount';
  }

  @override
  String get allSettled => 'All settled';

  @override
  String get dismiss => 'Dismiss';

  @override
  String get moneyTitle => 'Money';

  @override
  String get segTransactions => 'Transactions';

  @override
  String get segAccounts => 'Accounts';

  @override
  String get segBills => 'Bills & EMIs';

  @override
  String get segInvestments => 'Investments';

  @override
  String get searchHint => 'Search merchant or note';

  @override
  String get filterAll => 'All';

  @override
  String get filterOut => 'Spent';

  @override
  String get filterIn => 'Received';

  @override
  String get addCash => 'Add cash entry';

  @override
  String get amountRupees => 'Amount (₹)';

  @override
  String get whatWasIt => 'What was it?';

  @override
  String get category => 'Category';

  @override
  String get changeCategory => 'Change category';

  @override
  String get splitWithGroup => 'Split with a group';

  @override
  String get noTransactions => 'No transactions found';

  @override
  String get owedOnCard => 'Owed';

  @override
  String get limitLabel => 'Limit';

  @override
  String emisLeft(int n) {
    return '$n EMIs left';
  }

  @override
  String get outstanding => 'Outstanding';

  @override
  String get invested => 'Invested';

  @override
  String get approx => 'approx.';

  @override
  String get noBills => 'Nothing due soon';

  @override
  String get noInvestments => 'No investments linked';

  @override
  String get mascotTalk => 'Talk';

  @override
  String get mascotNoticed => 'Noticed';

  @override
  String get mascotPulse => 'Pulse';

  @override
  String get typeHint => 'Ask about your money';

  @override
  String get micStart => 'Tap to talk';

  @override
  String get micStop => 'Tap to stop';

  @override
  String get connecting => 'Connecting';

  @override
  String get voiceOffNote =>
      'Voice comes on when the live key is set. Type to chat.';

  @override
  String get mascotOffline =>
      'Poko needs the internet. Your numbers are still here.';

  @override
  String get confirmCardNote => 'Nothing happens until you tap Confirm.';

  @override
  String get proposalDone => 'Done. Your numbers are updated.';

  @override
  String get proposalFailed => 'That couldn\'t be done. Nothing was changed.';

  @override
  String get promptToday => 'How much can I spend today?';

  @override
  String get promptSpend => 'Where is my money going?';

  @override
  String get promptNotice => 'What did you notice?';

  @override
  String get promptFund => 'Should I buy this fund?';

  @override
  String get promptBills => 'Put my bills first';

  @override
  String get pulseEmpty => 'No Pulse yet today';

  @override
  String get pulseEmptyBody =>
      'Markets and world news with sources will appear here.';

  @override
  String get planTitle => 'Plan';

  @override
  String get suggested => 'Suggested moves';

  @override
  String get newPocket => 'New pocket';

  @override
  String get newGoal => 'New goal';

  @override
  String get nameLabel => 'Name';

  @override
  String get monthlyLimit => 'Monthly limit (₹)';

  @override
  String get targetAmount => 'Target (₹)';

  @override
  String get pausePocket => 'Pause';

  @override
  String get resumePocket => 'Resume';

  @override
  String needPerMonth(String amount) {
    return 'Needs $amount a month';
  }

  @override
  String byDate(String date) {
    return 'by $date';
  }

  @override
  String get noPockets => 'No pockets yet';

  @override
  String get noGoals => 'No goals yet';

  @override
  String get collabTitle => 'Collab';

  @override
  String get newGroup => 'New group';

  @override
  String get joinGroup => 'Join with a code';

  @override
  String get inviteCode => 'Invite code';

  @override
  String get groupName => 'Group name';

  @override
  String get typeFamily => 'Family';

  @override
  String get typeTrip => 'Trip';

  @override
  String get typeFlatmates => 'Flatmates';

  @override
  String get typeCustom => 'Custom';

  @override
  String get members => 'Members';

  @override
  String get expenses => 'Expenses';

  @override
  String get settleUp => 'Settle up';

  @override
  String get addExpense => 'Add expense';

  @override
  String get paidBy => 'Paid by';

  @override
  String get splitEqual => 'Split equally';

  @override
  String get addGuest => 'Add a guest';

  @override
  String get guestUpi => 'UPI ID (optional)';

  @override
  String get payByUpi => 'Pay by UPI';

  @override
  String get openUpiApp => 'Open UPI app';

  @override
  String get copyUpiId => 'Copy UPI ID';

  @override
  String get copied => 'Copied';

  @override
  String get markPaid => 'I\'ve paid';

  @override
  String get confirmReceived => 'Confirm received';

  @override
  String pays(String from, String to) {
    return '$from pays $to';
  }

  @override
  String get pocketNeverHolds =>
      'Pocket never holds money. You pay in your own UPI app.';

  @override
  String get demoUpiNote =>
      'Demo UPI IDs (@pocketdemo) are not real, so no money will move.';

  @override
  String get sharedBudget => 'Shared budget';

  @override
  String get pot => 'Pot';

  @override
  String get addToPot => 'Add to pot';

  @override
  String get privacyGroup => 'What this group sees';

  @override
  String get privacyGroupNote =>
      'Nothing of yours is shared unless you turn it on.';

  @override
  String get shareNothing => 'Sharing nothing';

  @override
  String get noGroups => 'No groups yet';

  @override
  String get noGroupsBody => 'Start one for a trip, your flat or your family.';

  @override
  String get you => 'You';

  @override
  String get guest => 'Guest';

  @override
  String get statusPending => 'Pending';

  @override
  String get statusLinkOpened => 'Link opened';

  @override
  String get statusMarkedPaid => 'Marked paid';

  @override
  String get statusConfirmed => 'Confirmed';

  @override
  String yourShare(String amount) {
    return 'Your share $amount';
  }

  @override
  String membersCount(int n) {
    return '$n members';
  }

  @override
  String get profileTitle => 'Profile';

  @override
  String get language => 'Language';

  @override
  String get mascotVoice => 'Poko\'s voice';

  @override
  String get nudgesTitle => 'Nudges';

  @override
  String get nudgesPerDay => 'Nudges a day';

  @override
  String get quietHours => 'Quiet hours';

  @override
  String get privacy => 'Privacy';

  @override
  String get exportData => 'Export my data';

  @override
  String get deleteData => 'Delete my data';

  @override
  String get deleteConfirm =>
      'This removes everything about you from Pocket. It can\'t be undone.';

  @override
  String get disclaimerTitle => 'Data, not advice';

  @override
  String get disclaimerBody =>
      'Pocket shows your own numbers and general explanations. It never tells you to buy, sell or switch any investment. All data in this build is synthetic.';

  @override
  String get switchPersona => 'Switch demo profile';

  @override
  String get demoTools => 'Demo tools';

  @override
  String get injectSwiggy => 'Add a Swiggy order now';

  @override
  String get linkedAccounts => 'Linked accounts';

  @override
  String get startOver => 'Start over';

  @override
  String exported(int n) {
    return 'Export ready: $n transactions';
  }

  @override
  String get muteVoice => 'Mute voice';
}
