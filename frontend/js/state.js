const appState = {
  language: 'fr',
  mission: null,
  latestMeasurement: null,
  map: [],
  recommendations: null,
  weather: null,
};

const I18N = {
  fr: {
    title: 'Vue mission',
    subtitle: 'Suivi temps réel du robot, des capteurs et des recommandations.',
    ask: 'Posez votre question...',
    botIntro: 'Bonjour. Je peux expliquer l’état du champ, la prochaine action et les cultures recommandées.',
  },
  ar: {
    title: 'واجهة المهمة',
    subtitle: 'متابعة مباشرة للروبوت والقياسات والتوصيات.',
    ask: 'اكتب سؤالك...',
    botIntro: 'مرحباً. أستطيع شرح حالة الحقل والإجراء التالي والمحاصيل المقترحة.',
  },
  da: {
    title: 'واجهة الميسيون',
    subtitle: 'تتبع مباشر ديال الروبو والقياسات والنصايح.',
    ask: 'كتب سؤالك...',
    botIntro: 'سلام. نقدر نشرح ليك حالة الحقل، الخطوة الجاية، والمحاصيل المناسبة.',
  },
};
