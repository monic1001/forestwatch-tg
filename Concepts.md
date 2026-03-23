# Ajout d'informations spectrales : les indices NDVI, NDBI et NDWI

||||||
|---|----|---|---|---|
| **Indice** | *NDVI* (Normalized Difference Vegetation Index) |  *NDBI* (Normalized Difference Built-up Index) | *NDWI* (Normalized Difference Water Index) | *Texture* (Indice spatial) |
| **Formule** | (B8 - B4) / (B8 + B4) | (B11 - B8) / (B11 + B8) | (B3 - B8) / (B3 + B8) | Calculée sur une fenêtre locale (ex. GLCM, moyenne, variance) |
| **Bande Sentinel-2** | *B8* (NIR, 842 nm)  <br> *B4* (RED, 665 nm) | *B11* (SWIR, 1610 nm) <br> *B8* (NIR, 842 nm) | *B3* (GREEN, 560 nm) <br> *B8* (NIR, 842 nm) | B4, B8, B11, NDVI, etc.      |
| **Compréhension** | Il mesure la densité et la vigueur de la végétation en comparant les bandes spectrales du proche infrarouge (NIR) et du rouge (RED). Plus la valeur du NDVI est élevée, plus la végétation est dense et en bonne santé. | Il sert à détecter les zones urbaines en comparant la réflectance du proche infrarouge (NIR) et du moyen infrarouge (SWIR). Les valeurs élevées du NDBI indiquent des zones construites comme les bâtiments et les infrastructures urbaines. | Il permet de détecter les surfaces en eau, en utilisant les bandes spectrales du proche infrarouge (NIR) et du moyen infrarouge (SWIR). Les valeurs élevées du NDWI correspondent aux étendues d’eau, ce qui le rend utile pour la gestion des ressources hydriques et la surveillance des zones inondables | Mesure la structure spatiale : homogénéité, contraste, régularité |
|**Application**| Évaluer la santé et la densité de la végétation | Détecter les zones urbaines et les infrastructures | Identifier les plans d'eau et les zones humides | Classification, segmentation, analyse de paysage |

<br>

**Revenons sur la texture :**

Les deux techniques de texture que nous utiliseront : <br>
**GLCM** (*Gray Level Co-occurrence Matrix*) : très riche, extraie descripteurs comme contraste, entropie, corrélation, homogénéité… <br>
**Moyenne / Variance locale** : plus simple et plus rapide, utile quand la texture est moins complexe ou pour du pré-filtrage.


| Bande  | **Moyenne/Variance locale** | **GLCM** | **Raison**                                                                                                                                                      |
|--------|-----------------------------|----------|----------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **NDVI** | Oui                         | Oui      | **Moy/Var locale** pour analyser la régularité de la végétation à petite échelle. **GLCM** pour détecter la texture fine des forêts et zones dégradées.      |
| **NDWI** | Oui                         | Oui      | **Moy/Var locale** pour mesurer la variabilité des surfaces d'eau. **GLCM** pour capturer la rugosité des zones d'eau ou de transition entre eau et végétation.  |
| **NDBI** | Non                         | Oui      | **GLCM** pour analyser la texture des zones urbaines (bâtiments, routes). Pas de **Moy/Var locale** car les zones urbaines sont déjà très hétérogènes.             |
| **B4 (Bleu)** | Oui                     | Non      | **Moy/Var locale** utile pour évaluer la variabilité des sols nus ou semi-arides. Pas de **GLCM** car la texture fine n'est pas cruciale ici.  |
| **B8 (NIR)** | Non                      | Oui      | **GLCM** pour capturer les variations fines dans la végétation (forêts denses vs clairsemées). Pas de **Moy/Var locale** car le **NDVI** est déjà suffisant.|
| **B12 (SWIR)** | Non                     | Oui      | **GLCM** pour analyser la texture des zones dégradées par la déforestation ou les incendies. Pas de **Moy/Var locale** car les textures fines sont plus significatives ici. |

<br>

**Les métriques GLCM sont diverses et permettent de caractériser différents aspects des textures dans les images. Voici les métriques les plus courantes :**

  | **Métrique**                  | **Description**                                                                                  |
|-------------------------------|--------------------------------------------------------------------------------------------------|
| **Contrast**                   | Mesure les différences d'intensité entre les pixels voisins.                                      |
| **Correlation**                | Mesure la relation linéaire entre les pixels voisins.                                              |
| **Energy**                     | Mesure l'uniformité de l'image, aussi appelée "angular second moment". Elle capture la régularité de la texture. |
| **Homogeneity**                | Mesure la proximité des pixels voisins dans l'image, indiquant l'homogénéité de la texture.       |
| **Dissimilarity**              | Mesure la différence d'intensité entre les pixels voisins. Plus la valeur est élevée, plus les pixels sont différents. |
| **Entropy**                    | Mesure la complexité ou l’imprévisibilité d'une texture. Plus l'entropie est élevée, plus la texture est complexe. |
| **Autocorrelation**            | Mesure la similitude des pixels voisins. Une texture régulière aura une forte autocorrélation.     |
| **Cluster Shade**              | Mesure l’asymétrie dans l’image, en particulier les ombres ou les zones fortement contrastées.    |
| **Cluster Prominence**         | Mesure la concentration des valeurs d'intensité dans l’image.                                    |
| **Maximum Probability**        | Mesure la probabilité maximale qu'un pixel appartienne à une classe d'intensité spécifique.        |
| **Variance**                   | Mesure la dispersion des intensités autour de la moyenne. Elle indique la variation de la texture. |
| **IDM (Inverse Difference Moment)** | Mesure la régularité dans l’image. Plus elle est faible, plus la texture est complexe.      |

<br><br>
<br><br>

---
---
---
---

<br><br>

# Extraction des bandes utiles

**Nous sélectionnerons les bandes utiles et les indices dérivés, et aussi les textures de ces sélections consernées :**


    NDVI,  NDWI*, NDBI, Red, NIR, SWIR puis les moy/var et textures validées plus haut.


**Nous n'allons toutefois pas travailler avec tous les métriques de glcm. Voici donc la selection que nous effectuons :**
<br>

| **Métrique**                  | **Description**                                                                                  | **Choix** | **Justification du Choix**                                                                                                                                                    | **Type**            |
|-------------------------------|--------------------------------------------------------------------------------------------------|-----------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|---------------------|
| **Contrast**                   | Mesure la différence d'intensité entre les pixels voisins.                                         | Oui       | Utilisé pour identifier les **transitions nettes** dans des zones comme les **zones urbaines** et **construites** (ex. **NDBI** et **B4**), où les contrastes sont marqués.         | De base             |
| **Energy**                     | Mesure l'uniformité d'une texture.                                                                | Oui       | Utile pour classer des zones homogènes comme la **végétation dense** (**NDVI**) ou **eau** (**NDWI**), où la texture est régulière et uniforme.                                | De base             |
| **Dissimilarity**              | Mesure la différence absolue d'intensité entre les pixels voisins.                                | Oui       | Permet de capturer les zones **perturbées** ou **irrégulières**, comme les **forêts dégradées** et zones urbaines, où les intensités varient fortement.                        | De base             |
| **Entropy**                    | Mesure la complexité ou l’imprévisibilité d'une texture.                                          | Oui       | Captures les zones avec des textures complexes et **diverses**, comme les **zones urbaines** ou **perturbées** (liées aux indices comme **NDBI** et **B8**).                    | De base             |
| **Autocorrelation**            | Mesure la similitude entre un pixel et ses voisins.                                                | Non       | Moins utile ici pour des zones perturbées ou irrégulières. Utile pour des zones régulières, mais les autres métriques comme **Energy** le capturent déjà.                        | De base             |
| **Cluster Shade**              | Mesure l’asymétrie de la distribution des intensités dans l’image.                                 | Non       | Moins pertinent pour la classification de végétation ou eau. Plus adapté aux zones urbaines ou avec des formes géométriques asymétriques.                                        | Supplémentaire      |
| **Cluster Prominence**         | Mesure la concentration des intensités dans l’image.                                              | Non       | Moins pertinent pour votre tâche de classification, car elle est plus utile pour des zones **très concentrées** en intensité (ex. zones urbaines).                           | Supplémentaire      |
| **Maximum Probability**        | Mesure la probabilité d'un pixel d'appartenir à un certain niveau d'intensité.                    | Non       | Moins discriminante pour des zones avec des textures variées. Préférable pour des zones **uniformes**, mais déjà couvert par **Energy**.                                        | Supplémentaire      |
| **Variance**                   | Mesure la dispersion des intensités dans l'image.                                                 | Non       | Peut être redondante avec **Dissimilarity** qui capture déjà les variations. Plus utile pour des zones avec une grande **variabilité d'intensité** (ex. forêts perturbées).      | Supplémentaire      |
| **IDM (Inverse Difference Moment)** | Mesure la régularité de l'image.                                                                  | Non       | Moins adaptée ici, car elle est plus adaptée à des zones très régulières. Cela peut être capturé par des métriques comme **Energy** et **Autocorrelation**.              | Supplémentaire      |

<br><br>
<br><br>

---
---
---
---

<br><br>

# Ajustement des classes

*La carte (la colonne Map) que nous venons de charger contient des classes décrivant le type de surface terrestre pour chaque point.*

Voici un tableau récapitulatif des 11 classes de couverture terrestre disponibles dans le produit ESA WorldCover v200 (2021),<br> qui propose une cartographie mondiale à une résolution de 10 mètres. Ces classes permettent de distinguer différents types de surfaces terrestres,<br> allant des forêts et zones agricoles aux zones urbaines et plans d'eau.

| Code | Classe                    | Description                       | Couleur HEX |
|------|---------------------------|-----------------------------------|-------------|
| 10   | Tree cover                | Forêts, plantations boisées       | #006400    |
| 20   | Shrubland                 | Buissons, maquis, landes          | #FFBB22     |
| 30   | Grassland                 | Prairies, savanes, pâturages      | #FFFF4C     |
| 40   | Cropland                  | Cultures agricoles                | #F096FF     |
| 50   | Built-up area             | Zones urbaines, constructions     | #FA0000     |
| 60   | Bare/sparse vegetation    | Sols nus, végétation clairsemée   | #B4B4B4     |
| 70   | Snow and ice              | Neige et glace                    | #F0F0F0     |
| 80   | Permanent water bodies    | Lacs, rivières, océans            | #0064C8     |
| 90   | Herbaceous wetland        | Zones humides herbacées           | #0096A0     |
| 95   | Mangroves                 | Forêts de mangrove                | #00CF75     |
| 100  | Moss and lichen           | Mousses et lichens                | #FAE6A0     |


*Mais pour notre travail, nous ne voulons avoir que sept classes :*

| Code | Classe                  | Description|
|--|--|--|
| 0     | Forêts, plantations boisées | Zones forestières et plantations boisées |
| 1     | Buissons, maquis, landes | Zones de buissons, maquis ou landes |
| 2     | Prairies, savanes, pâturages | Zones herbeuses comme les prairies ou savanes |
| 3     | Cultures agricoles | Zones dédiées à l'agriculture |
| 4     | Zones urbaines, constructions | Zones urbaines ou avec des constructions humaines |
| 5     | Sols nus, végétation clairsemée | Sols nus ou zones avec une couverture végétale clairsemée |
| 6     | Lacs, rivières, océans | Corps d'eau permanents comme les lacs et rivières |


D'où nous faisons cet ajustement : 

| Code Ancien | Code Nouveau |
|-------------|--------------|
| 10                | 0           |
| 20                | 1           |
| 30                | 2           |
| 40                | 3           |
| 50                | 4           |
| 60                | 5           |
| 80                | 6           |
| 70, 90, 95, 100   |-1           |


puis retirons les -1

