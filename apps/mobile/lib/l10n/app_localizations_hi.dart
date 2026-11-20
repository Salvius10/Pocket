// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for Hindi (`hi`).
class LHi extends L {
  LHi([String locale = 'hi']) : super(locale);

  @override
  String get appName => 'पॉकेट';

  @override
  String get tabHome => 'होम';

  @override
  String get tabMoney => 'पैसा';

  @override
  String get tabMascot => 'पोको';

  @override
  String get tabPlan => 'प्लान';

  @override
  String get tabCollab => 'साथ में';

  @override
  String get retry => 'फिर कोशिश करें';

  @override
  String get cancel => 'रद्द करें';

  @override
  String get confirm => 'कन्फर्म';

  @override
  String get notNow => 'अभी नहीं';

  @override
  String get done => 'हो गया';

  @override
  String get save => 'सेव करें';

  @override
  String get add => 'जोड़ें';

  @override
  String get continueLabel => 'आगे बढ़ें';

  @override
  String get skip => 'छोड़ें';

  @override
  String offlineBanner(String time) {
    return 'ऑफ़लाइन। $time तक के आँकड़े दिख रहे हैं।';
  }

  @override
  String asOf(String time) {
    return '$time तक';
  }

  @override
  String get errorTitle => 'कुछ गड़बड़ हो गई';

  @override
  String get errorBody => 'यह लोड नहीं हो पाया। कनेक्शन जाँचकर फिर कोशिश करें।';

  @override
  String get onbTagline => 'पैसा, जो खुद अपनी बात समझाए।';

  @override
  String get onbPickLanguage => 'अपनी भाषा चुनें';

  @override
  String get onbLangHint => 'इसे बाद में प्रोफ़ाइल में बदल सकते हैं।';

  @override
  String get onbTryDemo => 'डेमो प्रोफ़ाइल आज़माएँ';

  @override
  String get onbDemoNote => 'सिर्फ़ डेमो डेटा। कोई असली बैंक नहीं जुड़ा है।';

  @override
  String get onbVoiceTitle => 'पोको की आवाज़ चुनें';

  @override
  String get voiceWarm => 'गर्मजोश';

  @override
  String get voiceBright => 'चहकती';

  @override
  String get voiceCalm => 'शांत';

  @override
  String get voiceClear => 'साफ़';

  @override
  String get onbTalkTitle => 'पोको को अपने पैसों के बारे में बताइए';

  @override
  String get onbTalkHint => 'चार छोटे सवाल। लिखें या बोलें।';

  @override
  String get onbSkipTalk => 'बातचीत छोड़ें';

  @override
  String get onbPickPersona => 'अपने सबसे करीब की प्रोफ़ाइल चुनें';

  @override
  String get onbPersonaNote => 'हर प्रोफ़ाइल काल्पनिक है, साल भर के असली जैसे लेन-देन के साथ।';

  @override
  String get onbSuggested => 'सबसे करीब';

  @override
  String get onbBuild => 'मेरा होम बनाओ';

  @override
  String get onbBuilding => 'आपका होम बन रहा है';

  @override
  String onbStep(int n, int total) {
    return 'चरण $n / $total';
  }

  @override
  String get greetMorning => 'सुप्रभात';

  @override
  String get greetAfternoon => 'नमस्ते';

  @override
  String get greetEvening => 'शुभ संध्या';

  @override
  String get safeToSpend => 'आज खर्च कर सकते हैं';

  @override
  String get perDay => 'रोज़';

  @override
  String get leftToday => 'आज बचा';

  @override
  String get spentToday => 'आज खर्च';

  @override
  String daysLeft(int n) {
    return '$n दिन बाकी';
  }

  @override
  String overToday(String amount) {
    return 'आज की रकम से $amount ज़्यादा';
  }

  @override
  String get nothingLeft => 'इस महीने खुलकर खर्च करने को कुछ नहीं बचा';

  @override
  String get stsIncome => 'आय';

  @override
  String get stsCommitted => 'बिल और ईएमआई';

  @override
  String get stsGoals => 'लक्ष्य';

  @override
  String get stsSpent => 'खर्च';

  @override
  String get stsFormula => 'आय में से बिल और लक्ष्य घटाकर, फिर अब तक का खर्च घटाकर, बचे दिनों में बाँटा गया।';

  @override
  String get wPockets => 'पॉकेट';

  @override
  String get wGoals => 'लक्ष्य';

  @override
  String get wSpend => 'पैसा कहाँ गया';

  @override
  String get wCashFlow => 'आना-जाना';

  @override
  String get wTransactions => 'हाल के';

  @override
  String get wBills => 'बिल और ईएमआई';

  @override
  String get wNetWorth => 'कुल संपत्ति';

  @override
  String get wInvestments => 'निवेश';

  @override
  String get wInsight => 'पोको ने देखा';

  @override
  String get wPulse => 'पल्स';

  @override
  String get wGroup => 'ग्रुप';

  @override
  String get whyLayout => 'यह लेआउट क्यों?';

  @override
  String get whyLayoutTitle => 'आपका होम ऐसा क्यों है';

  @override
  String get editHome => 'होम बदलें';

  @override
  String get editHomeHint => 'खींचकर क्रम बदलें। सेफ़-टू-स्पेंड ऊपर ही रहेगा।';

  @override
  String get resetHome => 'पोको का लेआउट वापस लाएँ';

  @override
  String get askPokoChange => 'पोको से बदलवाएँ';

  @override
  String get homeSaved => 'होम सेव हो गया';

  @override
  String ofLimit(String limit) {
    return '$limit में से';
  }

  @override
  String leftLabel(String amount) {
    return '$amount बचा';
  }

  @override
  String overLabel(String amount) {
    return '$amount ज़्यादा';
  }

  @override
  String get statusOver => 'पार';

  @override
  String get statusWatch => 'ध्यान दें';

  @override
  String get statusOk => 'ठीक';

  @override
  String get statusBehind => 'पीछे';

  @override
  String get statusReached => 'पूरा';

  @override
  String get statusPaused => 'रुका';

  @override
  String get thisMonth => 'इस महीने';

  @override
  String get income => 'आया';

  @override
  String get spend => 'गया';

  @override
  String dueIn(int n) {
    return '$n दिन में';
  }

  @override
  String get dueToday => 'आज';

  @override
  String get dueTomorrow => 'कल';

  @override
  String get overdue => 'बकाया';

  @override
  String get autopay => 'ऑटो';

  @override
  String get assets => 'आपके पास';

  @override
  String get liabilities => 'आप पर बकाया';

  @override
  String get weekChange => 'इस हफ्ते';

  @override
  String get viewOnly => 'सिर्फ़ देखने के लिए। पॉकेट कभी खरीदने या बेचने को नहीं कहता।';

  @override
  String get noInsights => 'बताने लायक कुछ नया नहीं';

  @override
  String get noInsightsBody => 'पोको नज़र रख रहा है। पैटर्न यहाँ दिखेंगे।';

  @override
  String get forYou => 'आपके लिए';

  @override
  String youOwe(String amount) {
    return 'आपको $amount देने हैं';
  }

  @override
  String youAreOwed(String amount) {
    return 'आपको $amount मिलने हैं';
  }

  @override
  String get allSettled => 'हिसाब बराबर';

  @override
  String get dismiss => 'हटाएँ';

  @override
  String get moneyTitle => 'पैसा';

  @override
  String get segTransactions => 'लेन-देन';

  @override
  String get segAccounts => 'खाते';

  @override
  String get segBills => 'बिल और ईएमआई';

  @override
  String get segInvestments => 'निवेश';

  @override
  String get searchHint => 'दुकान या नोट खोजें';

  @override
  String get filterAll => 'सभी';

  @override
  String get filterOut => 'खर्च';

  @override
  String get filterIn => 'मिला';

  @override
  String get addCash => 'नकद एंट्री जोड़ें';

  @override
  String get amountRupees => 'रकम (₹)';

  @override
  String get whatWasIt => 'यह क्या था?';

  @override
  String get category => 'श्रेणी';

  @override
  String get changeCategory => 'श्रेणी बदलें';

  @override
  String get splitWithGroup => 'ग्रुप के साथ बाँटें';

  @override
  String get noTransactions => 'कोई लेन-देन नहीं मिला';

  @override
  String get owedOnCard => 'बकाया';

  @override
  String get limitLabel => 'सीमा';

  @override
  String emisLeft(int n) {
    return '$n ईएमआई बाकी';
  }

  @override
  String get outstanding => 'बाकी रकम';

  @override
  String get invested => 'लगाया';

  @override
  String get approx => 'लगभग';

  @override
  String get noBills => 'जल्द कुछ देना नहीं है';

  @override
  String get noInvestments => 'कोई निवेश जुड़ा नहीं है';

  @override
  String get mascotTalk => 'बात करें';

  @override
  String get mascotNoticed => 'देखा गया';

  @override
  String get mascotPulse => 'पल्स';

  @override
  String get typeHint => 'अपने पैसों के बारे में पूछें';

  @override
  String get micStart => 'बोलने के लिए टैप करें';

  @override
  String get micStop => 'रोकने के लिए टैप करें';

  @override
  String get connecting => 'जुड़ रहा है';

  @override
  String get voiceOffNote => 'लाइव की लगने पर आवाज़ चालू होगी। अभी लिखकर बात करें।';

  @override
  String get mascotOffline => 'पोको को इंटरनेट चाहिए। आपके आँकड़े यहीं हैं।';

  @override
  String get confirmCardNote => 'कन्फर्म टैप करने तक कुछ नहीं होगा।';

  @override
  String get proposalDone => 'हो गया। आपके आँकड़े अपडेट हो गए।';

  @override
  String get proposalFailed => 'यह नहीं हो पाया। कुछ नहीं बदला।';

  @override
  String get promptToday => 'आज कितना खर्च कर सकता हूँ?';

  @override
  String get promptSpend => 'मेरा पैसा कहाँ जा रहा है?';

  @override
  String get promptNotice => 'आपने क्या देखा?';

  @override
  String get promptFund => 'क्या मुझे यह फंड खरीदना चाहिए?';

  @override
  String get promptBills => 'मेरे बिल पहले रखो';

  @override
  String get pulseEmpty => 'आज का पल्स अभी नहीं आया';

  @override
  String get pulseEmptyBody => 'बाज़ार और दुनिया की खबरें स्रोत के साथ यहाँ दिखेंगी।';

  @override
  String get planTitle => 'प्लान';

  @override
  String get suggested => 'सुझाए गए बदलाव';

  @override
  String get newPocket => 'नया पॉकेट';

  @override
  String get newGoal => 'नया लक्ष्य';

  @override
  String get nameLabel => 'नाम';

  @override
  String get monthlyLimit => 'महीने की सीमा (₹)';

  @override
  String get targetAmount => 'लक्ष्य रकम (₹)';

  @override
  String get pausePocket => 'रोकें';

  @override
  String get resumePocket => 'चालू करें';

  @override
  String needPerMonth(String amount) {
    return 'हर महीने $amount चाहिए';
  }

  @override
  String byDate(String date) {
    return '$date तक';
  }

  @override
  String get noPockets => 'अभी कोई पॉकेट नहीं';

  @override
  String get noGoals => 'अभी कोई लक्ष्य नहीं';

  @override
  String get collabTitle => 'साथ में';

  @override
  String get newGroup => 'नया ग्रुप';

  @override
  String get joinGroup => 'कोड से जुड़ें';

  @override
  String get inviteCode => 'इनवाइट कोड';

  @override
  String get groupName => 'ग्रुप का नाम';

  @override
  String get typeFamily => 'परिवार';

  @override
  String get typeTrip => 'ट्रिप';

  @override
  String get typeFlatmates => 'फ़्लैटमेट';

  @override
  String get typeCustom => 'अन्य';

  @override
  String get members => 'सदस्य';

  @override
  String get expenses => 'खर्चे';

  @override
  String get settleUp => 'हिसाब चुकाएँ';

  @override
  String get addExpense => 'खर्च जोड़ें';

  @override
  String get paidBy => 'किसने दिया';

  @override
  String get splitEqual => 'बराबर बाँटें';

  @override
  String get addGuest => 'मेहमान जोड़ें';

  @override
  String get guestUpi => 'यूपीआई आईडी (वैकल्पिक)';

  @override
  String get payByUpi => 'यूपीआई से चुकाएँ';

  @override
  String get openUpiApp => 'यूपीआई ऐप खोलें';

  @override
  String get copyUpiId => 'यूपीआई आईडी कॉपी करें';

  @override
  String get copied => 'कॉपी हो गया';

  @override
  String get markPaid => 'मैंने चुका दिया';

  @override
  String get confirmReceived => 'मिल गया, कन्फर्म करें';

  @override
  String pays(String from, String to) {
    return '$from देंगे $to को';
  }

  @override
  String get pocketNeverHolds => 'पॉकेट कभी पैसा नहीं रखता। आप अपने यूपीआई ऐप से चुकाते हैं।';

  @override
  String get demoUpiNote => 'डेमो यूपीआई आईडी (@pocketdemo) असली नहीं हैं, इसलिए कोई पैसा नहीं जाएगा।';

  @override
  String get sharedBudget => 'साझा बजट';

  @override
  String get pot => 'पॉट';

  @override
  String get addToPot => 'पॉट में जोड़ें';

  @override
  String get privacyGroup => 'यह ग्रुप क्या देखता है';

  @override
  String get privacyGroupNote => 'जब तक आप चालू न करें, आपका कुछ भी साझा नहीं होता।';

  @override
  String get shareNothing => 'कुछ भी साझा नहीं';

  @override
  String get noGroups => 'अभी कोई ग्रुप नहीं';

  @override
  String get noGroupsBody => 'ट्रिप, फ़्लैट या परिवार के लिए एक शुरू करें।';

  @override
  String get you => 'आप';

  @override
  String get guest => 'मेहमान';

  @override
  String get statusPending => 'बाकी';

  @override
  String get statusLinkOpened => 'लिंक खुला';

  @override
  String get statusMarkedPaid => 'चुकाया बताया';

  @override
  String get statusConfirmed => 'कन्फर्म';

  @override
  String yourShare(String amount) {
    return 'आपका हिस्सा $amount';
  }

  @override
  String membersCount(int n) {
    return '$n सदस्य';
  }

  @override
  String get profileTitle => 'प्रोफ़ाइल';

  @override
  String get language => 'भाषा';

  @override
  String get mascotVoice => 'पोको की आवाज़';

  @override
  String get nudgesTitle => 'नज';

  @override
  String get nudgesPerDay => 'दिन में कितने नज';

  @override
  String get quietHours => 'शांत समय';

  @override
  String get privacy => 'निजता';

  @override
  String get exportData => 'मेरा डेटा एक्सपोर्ट करें';

  @override
  String get deleteData => 'मेरा डेटा मिटाएँ';

  @override
  String get deleteConfirm => 'इससे पॉकेट से आपके बारे में सब कुछ हट जाएगा। इसे वापस नहीं लाया जा सकता।';

  @override
  String get disclaimerTitle => 'जानकारी, सलाह नहीं';

  @override
  String get disclaimerBody => 'पॉकेट आपके अपने आँकड़े और सामान्य जानकारी दिखाता है। यह कभी कोई निवेश खरीदने, बेचने या बदलने को नहीं कहता। इस बिल्ड का सारा डेटा बनावटी है।';

  @override
  String get switchPersona => 'डेमो प्रोफ़ाइल बदलें';

  @override
  String get demoTools => 'डेमो टूल';

  @override
  String get injectSwiggy => 'अभी एक स्विगी ऑर्डर जोड़ें';

  @override
  String get linkedAccounts => 'जुड़े खाते';

  @override
  String get startOver => 'शुरू से करें';

  @override
  String exported(int n) {
    return 'एक्सपोर्ट तैयार: $n लेन-देन';
  }

  @override
  String get muteVoice => 'आवाज़ बंद करें';

  @override
  String get smsTitle => 'अभी एक बैंक SMS आया';

  @override
  String get smsReadAs => 'पॉकेट ने इसे ऐसे पढ़ा';

  @override
  String get smsSynthetic => 'यह संदेश डेमो के लिए बनाया गया है। पॉकेट आपके फ़ोन के SMS नहीं पढ़ता।';

  @override
  String get smsSeeHome => 'होम पर देखें';
}
