"""Turma role names as shown in the role tooltip, per game country code.

Data collected by the authors of GladiatusPlayerStatsAPI (DinoDevs, LGPL-3.0):
https://github.com/DinoDevs/GladiatusPlayerStatsAPI
"""
ROLE_TEXTS = {
    'ae': {'tank': 'مهمة: إثارة الانتباه', 'dps': 'مهمة: توزيع الضرر', 'healer': 'مهمة: معالجة أعضاء المجموعة', 'out': 'مهمة: لا تأخده معك'},
    'ar': {'tank': 'Misión: Ocupate de vos mismo', 'dps': 'Misión: Distribuí el daño', 'healer': 'Misión: Curá a los miembros de tu grupo', 'out': 'Misión: No te lleves'},
    'ba': {'tank': 'Zadatak: Usmjeri pozornost prema sebi.', 'dps': 'Zadatak: Isperi štetu', 'healer': 'Zadatak: Izlječi grupu', 'out': 'Zadatak: Nemoj uzeti sa'},
    'bg': {'tank': 'Куест: Насочи вниманието към себе си', 'dps': 'Куест: Прави поражение', 'healer': 'Куест: Лекувайте членове на групата', 'out': 'Куест: Не вземай участие'},
    'br': {'tank': 'Missão: Atenção direta a si', 'dps': 'Missão: Prato de danos', 'healer': 'Missão: Curar membros do grupos', 'out': 'Missão: Não tome com'},
    'cz': {'tank': 'Úkol: Přitáhni na sebe pozornost', 'dps': 'Úkol: Rozdávej rány', 'healer': 'Úkol: Uzdrav členy družiny', 'out': 'Úkol: Nezahrávej si s'},
    'de': {'tank': 'Aufgabe: Aufmerksamkeit auf sich ziehen', 'dps': 'Aufgabe: Schaden austeilen', 'healer': 'Aufgabe: Gruppenmitglieder heilen', 'out': 'Aufgabe: Nicht mitnehmen'},
    'dk': {'tank': 'Opgave: Rette opmærksomheden mod én selv', 'dps': 'Opgave: Uddel skade', 'healer': 'Opgave: Heal gruppemedlemmer', 'out': 'Opgave: Tag ikke med'},
    'ee': {'tank': 'Retk: Otsene tähelepanu endale', 'dps': 'Retk: Ründesse', 'healer': 'Retk: Ravi grupi liikmeid', 'out': 'Retk: Ära võta ühes'},
    'en': {'tank': 'Quest: Direct attention to oneself', 'dps': 'Quest: Dish out damage', 'healer': 'Quest: Heal group members', 'out': 'Quest: Do not take with'},
    'es': {'tank': 'Misión: Llamar la atención', 'dps': 'Misión: Reparte el daño', 'healer': 'Misión: Curar miembros del grupo', 'out': 'Misión: Sin utilizar'},
    'fi': {'tank': 'Tehtävä: Kerää huomion itseensä', 'dps': 'Tehtävä: Tekee vauriota', 'healer': 'Tehtävä: Parantaa ryhmän jäseniä', 'out': 'Tehtävä: Ei oteta mukaan'},
    'fr': {'tank': 'Mission : Attirer l`attention sur soi', 'dps': 'Mission : Infliger des dégâts', 'healer': 'Mission : Soigner les membres du groupe', 'out': 'Mission : Ne pas prendre avec soi'},
    'gr': {'tank': 'Αποστολή Πρόσεχε τον εαυτό σου', 'dps': 'Αποστολή Προβλεπόμενη ζημιά', 'healer': 'Αποστολή Θεραπεύστε τα μέλη της ομάδας σας', 'out': 'Αποστολή Μη πάρεις μαζί'},
    'hu': {'tank': 'Feladat: Ellenfél figyelmét magára vonja', 'dps': 'Feladat: Ellenfél támadása', 'healer': 'Feladat: Csapat tagjainak gyógyítása', 'out': 'Feladat: Tétlen'},
    'il': {'tank': 'משימה: תשומת לב על עצמו', 'dps': 'משימה: נזק במנות', 'healer': 'משימה: רפא חברי קבוצה', 'out': 'משימה: אל תקח עם'},
    'it': {'tank': 'Incarico: Attrae l`attenzione su di sé', 'dps': 'Incarico: Distribuisce i danni', 'healer': 'Incarico: Guarisce i membri del gruppo', 'out': 'Incarico: Disattivato'},
    'lt': {'tank': 'Užduotis: Tiesioginis dėmesys į save', 'dps': 'Užduotis: Dalinti žalą', 'healer': 'Užduotis: Pagydyti grupės narius', 'out': 'Užduotis: Neimti su'},
    'lv': {'tank': 'Uzdevums: Pievērs uzmanību pats sev', 'dps': 'Uzdevums: Izpostīt bojājumu', 'healer': 'Uzdevums: Dziedināt grupas biedrus', 'out': 'Uzdevums: Neņem ar'},
    'mx': {'tank': 'Tarea: Atención directa a uno mismo', 'dps': 'Tarea: Reparta el daño', 'healer': 'Tarea: Cura a los miembros del grupo', 'out': 'Tarea: No tomes'},
    'nl': {'tank': 'Quest: Richt de aandacht op jezelf', 'dps': 'Quest: Schade verdelen', 'healer': 'Quest: Groepsleden genezen', 'out': 'Quest: Niet meenemen'},
    'no': {'tank': 'Ekspedisjon: Diriger oppmerksomhet til seg selv', 'dps': 'Ekspedisjon: Server ut skade', 'healer': 'Ekspedisjon: Helbred gruppe medlemmer', 'out': 'Ekspedisjon: Ikke ta med'},
    'pl': {'tank': 'Zadanie: Prowokuj przeciwnika', 'dps': 'Zadanie: Atakuj', 'healer': 'Zadanie: Uzdrawiaj członków grupy', 'out': 'Zadanie: Usuń z grupy'},
    'pt': {'tank': 'Missão: Chama a atenção para si mesmo', 'dps': 'Missão: Reparte o dano', 'healer': 'Missão: Cura os membros do grupo', 'out': 'Missão: Não tome com'},
    'ro': {'tank': 'Cercetare: Atentie directa de sine', 'dps': 'Cercetare: Distribuie daunele', 'healer': 'Cercetare: Vindeca membrii grupului', 'out': 'Cercetare: Fara a folosi'},
    'ru': {'tank': 'Задание: Защищать', 'dps': 'Задание: Наносить урон', 'healer': 'Задание: Лечить членов группы', 'out': 'Задание: Не использовать'},
    'se': {'tank': 'Uppgift: Tar emot skada', 'dps': 'Uppgift: Dela ut skada', 'healer': 'Uppgift: Läker gruppmedlemmar', 'out': 'Uppgift: Ta inte med'},
    'sk': {'tank': 'Úloha: Upútať pozornosť', 'dps': 'Úloha: Rozdávať zranenia', 'healer': 'Úloha: Liečiť', 'out': 'Úloha: Nevziať'},
    'tr': {'tank': 'Görev: Dikkati kendi üzerine çekmek', 'dps': 'Görev: Hasarı paylaştır', 'healer': 'Görev: Grup üyelerini iyileştir', 'out': 'Görev: Beraberinde alma'},
    'tw': {'tank': '任務: 吸引攻擊', 'dps': '任務: 實施攻擊', 'healer': '任務: 負責治癒', 'out': '任務: 不加入隊伍'},
    'us': {'tank': 'Task: Direct attention to oneself', 'dps': 'Task: Dish out damage', 'healer': 'Task: Heal group members', 'out': 'Task: Do not take with'},
}
