# Thomas Baignères - Olvid - Concurrencer WhatsApp sans collecter une seule donnée

- Host: Léna
- Guest: Thomas Baignères

**Léna** [00:04]: Bonjour, je m'appelle Léna. Bienvenue sur mon podcast. Ici, je donne la parole aux dirigeants et aux entrepreneurs qui bâtissent la sécurité. A chaque épisode, je mets en avant un parcours et je décrypte comment ils naviguent dans cette industrie. Bonne écoute ! Bienvenue dans In Security We Trust. Ici, on accueille celles et ceux qui bâtissent la sécurité. Mon invité du jour a soutenu une thèse en cryptographie à l'EPFL en 2008. Pendant 7 ans, il a été expert crypto en cabinet de calcul des preuves des protocoles. En 2019, il monte Olvid avec trois autres cofondateurs, une messagerie sans annuaire, sans numéro de téléphone où le serveur ne voit rien. Et puis, novembre 2023, une circulaire de Matignon somme les ministres de désinstaller WhatsApp, Signal et Telegram et de passer sur Olvid. La plus sûre du monde, dit le gouvernement. 100 000 utilisateurs à l'époque face à WhatsApp et ses milliards. Un chercheur qui a dû apprendre à vendre. Voilà ce qu'on va démonter aujourd'hui. Thomas Baignères, bienvenue.

**Thomas Baignères** [01:04]: Merci, merci beaucoup de m'avoir invité.

**Léna** [01:06]: Avec plaisir. Je te laisse te présenter avec tes mots et compléter peut-être mon intro.

**Thomas Baignères** [01:10]: Tu as déjà tout dit. Donc oui, moi, je suis... A l'origine, je suis chercheur en cryptographie, donc effectivement, test de doctorat à l'EPFL. J'ai ensuite toujours été dans le milieu de la cryptographie, dans le cabinet de conseil. Alors, le cabinet de conseil, c'est une petite start-up qui s'appelle CryptoExperts, qui existe toujours d'ailleurs, qui va très bien, et qui n'engage que des docteurs en cryptographie, où ils font toujours d'ailleurs de la cryptographie sur mesure.
