/**
 * productos-data.js
 * Copia embebida de data/productos.json, usada como respaldo cuando el
 * sitio se abre directamente desde el disco (doble clic) y el navegador
 * bloquea la carga de productos.json por seguridad. El catálogo intenta
 * primero cargar productos.json (necesario para cuando el sitio esté en
 * un servidor real o conectado a una API); si eso falla, usa esta copia.
 *
 * IMPORTANTE: si actualizas data/productos.json, vuelve a generar este
 * archivo para que ambos queden sincronizados.
 */
const PRODUCTOS_DATA = [
  {
    "id": "vaj-001",
    "nombre": "Plato llano porcelana blanca",
    "categoria": "vajilla",
    "categoriaLabel": "Vajilla",
    "descripcion": "Plato llano de porcelana blanca, ideal para montajes clásicos y modernos.",
    "descripcionLarga": "Plato llano de porcelana blanca de borde fino, apto para cualquier estilo de montaje, desde matrimonios clásicos hasta eventos corporativos. Su diseño minimalista combina con cualquier mantelería y centro de mesa.",
    "dimensiones": "27 cm de diámetro",
    "material": "Porcelana",
    "capacidad": "Individual",
    "color": "Blanco",
    "precio": 900,
    "unidadPrecio": "por unidad / evento",
    "imagen": "/static/images/loza1.jpg",
    "imagenes": [
      "images/loza1.jpg"
    ],
    "destacado": true
  },
  {
    "id": "vaj-002",
    "nombre": "Plato de postre porcelana blanca",
    "categoria": "vajilla",
    "categoriaLabel": "Vajilla",
    "descripcion": "Plato de postre a juego con la línea de vajilla blanca clásica.",
    "descripcionLarga": "Plato de postre de porcelana blanca, complemento perfecto para el servicio de entrada o postre. Combina con toda la línea de vajilla blanca disponible para arriendo.",
    "dimensiones": "20 cm de diámetro",
    "material": "Porcelana",
    "capacidad": "Individual",
    "color": "Blanco",
    "precio": 650,
    "unidadPrecio": "por unidad / evento",
    "imagen": "images/loza1.jpg",
    "imagenes": [
      "images/loza1.jpg"
    ],
    "destacado": false
  },
  {
    "id": "vaj-003",
    "nombre": "Set de vajilla borde dorado",
    "categoria": "vajilla",
    "categoriaLabel": "Vajilla",
    "descripcion": "Vajilla de porcelana con fino borde dorado para montajes elegantes.",
    "descripcionLarga": "Set de vajilla de porcelana blanca con delicado filo dorado, pensado para matrimonios y celebraciones que buscan un toque de distinción sin caer en excesos. Incluye plato base, plato llano y plato de postre.",
    "dimensiones": "Plato base 32 cm / plato llano 27 cm / plato postre 20 cm",
    "material": "Porcelana con filo dorado",
    "capacidad": "Individual (set de 3 piezas)",
    "color": "Blanco con borde dorado",
    "precio": 1500,
    "unidadPrecio": "por set / evento",
    "imagen": "images/loza1.jpg",
    "imagenes": [
      "images/loza1.jpg"
    ],
    "destacado": true
  },
  {
    "id": "vaj-004",
    "nombre": "Plato base negro mate",
    "categoria": "vajilla",
    "categoriaLabel": "Vajilla",
    "descripcion": "Plato base de diseño moderno en color negro mate.",
    "descripcionLarga": "Plato base decorativo en color negro mate, perfecto para montajes contemporáneos y eventos empresariales que buscan un estilo sobrio y actual.",
    "dimensiones": "33 cm de diámetro",
    "material": "Cerámica",
    "capacidad": "Individual",
    "color": "Negro mate",
    "precio": 800,
    "unidadPrecio": "por unidad / evento",
    "imagen": "images/loza1.jpg",
    "imagenes": [
      "images/loza1.jpg"
    ],
    "destacado": false
  },
  {
    "id": "cris-001",
    "nombre": "Copa de vino tinto",
    "categoria": "cristaleria",
    "categoriaLabel": "Cristalería",
    "descripcion": "Copa de cristal transparente para vino tinto, diseño clásico.",
    "descripcionLarga": "Copa de cristal para vino tinto de diseño atemporal, con cáliz amplio que resalta los aromas. Ideal para matrimonios, cenas formales y eventos corporativos.",
    "dimensiones": "22 cm de alto / 450 ml",
    "material": "Cristal",
    "capacidad": "450 ml",
    "color": "Transparente",
    "precio": 500,
    "unidadPrecio": "por unidad / evento",
    "imagen": "images/copas1.jpg",
    "imagenes": [
      "images/copas1.jpg"
    ],
    "destacado": true
  },
  {
    "id": "cris-002",
    "nombre": "Copa de vino blanco",
    "categoria": "cristaleria",
    "categoriaLabel": "Cristalería",
    "descripcion": "Copa de cristal para vino blanco, cáliz más angosto.",
    "descripcionLarga": "Copa de cristal diseñada especialmente para vino blanco, con cáliz angosto que mantiene la temperatura ideal de la copa. Combina perfectamente con la copa de vino tinto de la misma línea.",
    "dimensiones": "20 cm de alto / 350 ml",
    "material": "Cristal",
    "capacidad": "350 ml",
    "color": "Transparente",
    "precio": 500,
    "unidadPrecio": "por unidad / evento",
    "imagen": "images/copas1.jpg",
    "imagenes": [
      "images/copas1.jpg"
    ],
    "destacado": false
  },
  {
    "id": "cris-003",
    "nombre": "Copa de champaña flauta",
    "categoria": "cristaleria",
    "categoriaLabel": "Cristalería",
    "descripcion": "Copa flauta de cristal para espumante y brindis.",
    "descripcionLarga": "Copa flauta de cristal transparente, diseñada para conservar las burbujas del espumante durante el brindis. Infaltable en matrimonios y celebraciones.",
    "dimensiones": "24 cm de alto / 200 ml",
    "material": "Cristal",
    "capacidad": "200 ml",
    "color": "Transparente",
    "precio": 550,
    "unidadPrecio": "por unidad / evento",
    "imagen": "images/copas1.jpg",
    "imagenes": [
      "images/copas1.jpg"
    ],
    "destacado": true
  },
  {
    "id": "cris-004",
    "nombre": "Vaso old fashioned",
    "categoria": "cristaleria",
    "categoriaLabel": "Cristalería",
    "descripcion": "Vaso bajo de cristal para tragos cortos y bebidas espirituosas.",
    "descripcionLarga": "Vaso old fashioned de cristal grueso, ideal para la barra de tragos en eventos empresariales y celebraciones. Resistente y de diseño clásico.",
    "dimensiones": "9 cm de alto / 320 ml",
    "material": "Cristal",
    "capacidad": "320 ml",
    "color": "Transparente",
    "precio": 450,
    "unidadPrecio": "por unidad / evento",
    "imagen": "images/copas1.jpg",
    "imagenes": [
      "images/copas1.jpg"
    ],
    "destacado": false
  },
  {
    "id": "cub-001",
    "nombre": "Set de cubiertos línea clásica",
    "categoria": "cubiertos",
    "categoriaLabel": "Cubiertos y servicio",
    "descripcion": "Set de cubiertos de acero inoxidable pulido, línea clásica.",
    "descripcionLarga": "Set de cubiertos de acero inoxidable con acabado espejo, incluye tenedor de fondo, tenedor de postre, cuchillo de fondo y cuchara sopera. Diseño clásico que combina con cualquier tipo de montaje.",
    "dimensiones": "Set de 4 piezas",
    "material": "Acero inoxidable",
    "capacidad": "Individual",
    "color": "Plateado",
    "precio": 700,
    "unidadPrecio": "por set / evento",
    "imagen": "images/cubiertos1.jpg",
    "imagenes": [
      "images/cubiertos1.jpg"
    ],
    "destacado": true
  },
  {
    "id": "cub-002",
    "nombre": "Cuchara de servicio grande",
    "categoria": "cubiertos",
    "categoriaLabel": "Cubiertos y servicio",
    "descripcion": "Cuchara de servicio para fuentes y buffet.",
    "descripcionLarga": "Cuchara de servicio de acero inoxidable, tamaño grande, ideal para el montaje de mesas de buffet y fuentes compartidas.",
    "dimensiones": "28 cm de largo",
    "material": "Acero inoxidable",
    "capacidad": "Servicio compartido",
    "color": "Plateado",
    "precio": 400,
    "unidadPrecio": "por unidad / evento",
    "imagen": "images/cubiertos1.jpg",
    "imagenes": [
      "images/cubiertos1.jpg"
    ],
    "destacado": false
  },
  {
    "id": "cub-003",
    "nombre": "Pinza de servicio",
    "categoria": "cubiertos",
    "categoriaLabel": "Cubiertos y servicio",
    "descripcion": "Pinza de acero inoxidable para servicio de buffet y ensaladas.",
    "descripcionLarga": "Pinza de servicio de acero inoxidable, práctica y resistente, pensada para el montaje de estaciones de comida y buffet en eventos empresariales y celebraciones.",
    "dimensiones": "24 cm de largo",
    "material": "Acero inoxidable",
    "capacidad": "Servicio compartido",
    "color": "Plateado",
    "precio": 400,
    "unidadPrecio": "por unidad / evento",
    "imagen": "images/cubiertos1.jpg",
    "imagenes": [
      "images/cubiertos1.jpg"
    ],
    "destacado": false
  },
  {
    "id": "mes-001",
    "nombre": "Mesa redonda para 10 personas",
    "categoria": "mesas-sillas",
    "categoriaLabel": "Mesas y sillas",
    "descripcion": "Mesa redonda plegable, ideal para banquetes y matrimonios.",
    "descripcionLarga": "Mesa redonda plegable de uso profesional, diseñada para el montaje de banquetes. Su tamaño permite acomodar cómodamente hasta 10 invitados con mantelería incluida.",
    "dimensiones": "Diámetro 1,5 m",
    "material": "Madera reforzada / estructura metálica",
    "capacidad": "10 personas",
    "color": "Madera natural",
    "precio": 15000,
    "unidadPrecio": "por unidad / evento",
    "imagen": "images/mesa-clean.jpg",
    "imagenes": [
      "images/mesa-clean.jpg"
    ],
    "destacado": true
  },
  {
    "id": "mes-002",
    "nombre": "Mesa rectangular imperial",
    "categoria": "mesas-sillas",
    "categoriaLabel": "Mesas y sillas",
    "descripcion": "Mesa rectangular ideal para montajes tipo imperial o family style.",
    "descripcionLarga": "Mesa rectangular plegable de gran formato, perfecta para montajes tipo mesa imperial en matrimonios o mesas directorio en eventos empresariales.",
    "dimensiones": "2,4 m x 0,9 m",
    "material": "Madera reforzada / estructura metálica",
    "capacidad": "8 a 10 personas",
    "color": "Madera natural",
    "precio": 18000,
    "unidadPrecio": "por unidad / evento",
    "imagen": "images/mesa-clean.jpg",
    "imagenes": [
      "images/mesa-clean.jpg"
    ],
    "destacado": false
  },
  {
    "id": "sil-001",
    "nombre": "Silla Tiffany transparente",
    "categoria": "mesas-sillas",
    "categoriaLabel": "Mesas y sillas",
    "descripcion": "Silla Tiffany en policarbonato transparente, ideal para matrimonios.",
    "descripcionLarga": "Silla Tiffany de policarbonato transparente, un clásico infaltable en matrimonios y celebraciones elegantes gracias a su diseño liviano que se integra a cualquier decoración.",
    "dimensiones": "90 cm de alto",
    "material": "Policarbonato",
    "capacidad": "Individual",
    "color": "Transparente",
    "precio": 2500,
    "unidadPrecio": "por unidad / evento",
    "imagen": "images/silla1.jpg",
    "imagenes": [
      "images/silla1.jpg"
    ],
    "destacado": true
  },
  {
    "id": "sil-002",
    "nombre": "Silla Chiavari madera",
    "categoria": "mesas-sillas",
    "categoriaLabel": "Mesas y sillas",
    "descripcion": "Silla Chiavari de madera con asiento acolchado, estilo clásico.",
    "descripcionLarga": "Silla Chiavari de madera natural con asiento acolchado removible, un clásico del montaje de matrimonios y eventos formales por su elegancia atemporal.",
    "dimensiones": "92 cm de alto",
    "material": "Madera",
    "capacidad": "Individual",
    "color": "Madera natural / cojín beige",
    "precio": 3200,
    "unidadPrecio": "por unidad / evento",
    "imagen": "images/silla1.jpg",
    "imagenes": [
      "images/silla1.jpg"
    ],
    "destacado": false
  },
  {
    "id": "man-001",
    "nombre": "Mantel redondo lino beige",
    "categoria": "manteleria",
    "categoriaLabel": "Mantelería",
    "descripcion": "Mantel redondo color beige, tela tipo lino, hasta el piso.",
    "descripcionLarga": "Mantel redondo en tela tipo lino color beige suave, con caída hasta el piso para un montaje elegante y prolijo. Combina naturalmente con la paleta cálida de la marca.",
    "dimensiones": "Para mesa de 1,5 m de diámetro",
    "material": "Tela tipo lino",
    "capacidad": "Mesa redonda 10 personas",
    "color": "Beige",
    "precio": 12000,
    "unidadPrecio": "por unidad / evento",
    "imagen": "images/manteleria1.jpg",
    "imagenes": [
      "images/manteleria1.jpg"
    ],
    "destacado": true
  },
  {
    "id": "man-002",
    "nombre": "Mantel rectangular blanco",
    "categoria": "manteleria",
    "categoriaLabel": "Mantelería",
    "descripcion": "Mantel rectangular blanco, tela satinada, uso clásico y formal.",
    "descripcionLarga": "Mantel rectangular en tela satinada color blanco, ideal para mesas imperiales y montajes formales de eventos empresariales y matrimonios.",
    "dimensiones": "Para mesa de 2,4 m x 0,9 m",
    "material": "Tela satinada",
    "capacidad": "Mesa rectangular 8-10 personas",
    "color": "Blanco",
    "precio": 14000,
    "unidadPrecio": "por unidad / evento",
    "imagen": "images/manteleria1.jpg",
    "imagenes": [
      "images/manteleria1.jpg"
    ],
    "destacado": false
  },
  {
    "id": "man-003",
    "nombre": "Camino de mesa lino natural",
    "categoria": "manteleria",
    "categoriaLabel": "Mantelería",
    "descripcion": "Camino de mesa en lino natural, complemento decorativo.",
    "descripcionLarga": "Camino de mesa en tela de lino color natural, pensado como complemento decorativo sobre mantelería blanca o beige, aportando textura al montaje.",
    "dimensiones": "3 m x 0,4 m",
    "material": "Lino",
    "capacidad": "Mesa redonda o rectangular",
    "color": "Natural",
    "precio": 5000,
    "unidadPrecio": "por unidad / evento",
    "imagen": "images/manteleria1.jpg",
    "imagenes": [
      "images/manteleria1.jpg"
    ],
    "destacado": false
  },
  {
    "id": "man-004",
    "nombre": "Servilleta de tela beige",
    "categoria": "manteleria",
    "categoriaLabel": "Mantelería",
    "descripcion": "Servilleta de tela color beige, a juego con la mantelería.",
    "descripcionLarga": "Servilleta de tela color beige suave, confeccionada con el mismo material que la mantelería de la línea, para un montaje coordinado y cálido.",
    "dimensiones": "45 cm x 45 cm",
    "material": "Tela tipo lino",
    "capacidad": "Individual",
    "color": "Beige",
    "precio": 350,
    "unidadPrecio": "por unidad / evento",
    "imagen": "images/manteleria1.jpg",
    "imagenes": [
      "images/manteleria1.jpg"
    ],
    "destacado": false
  },
  {
    "id": "car-001",
    "nombre": "Carpa blanca 10x10 m",
    "categoria": "carpas-exteriores",
    "categoriaLabel": "Carpas y exteriores",
    "descripcion": "Carpa blanca de estructura, ideal para matrimonios en exteriores.",
    "descripcionLarga": "Carpa blanca de estructura metálica y lona traslúcida, pensada para montajes de matrimonios y eventos al aire libre. Incluye paredes laterales opcionales según condiciones climáticas.",
    "dimensiones": "10 m x 10 m (100 m²)",
    "material": "Estructura metálica y lona",
    "capacidad": "Hasta 80 personas sentadas",
    "color": "Blanco",
    "precio": 350000,
    "unidadPrecio": "por evento (instalación incluida)",
    "imagen": "images/carpa1.jpg",
    "imagenes": [
      "images/carpa1.jpg"
    ],
    "destacado": true
  },
  {
    "id": "car-002",
    "nombre": "Toldo lateral desmontable",
    "categoria": "carpas-exteriores",
    "categoriaLabel": "Carpas y exteriores",
    "descripcion": "Toldo lateral para complementar carpas en caso de viento o lluvia.",
    "descripcionLarga": "Toldo lateral desmontable de lona resistente, ideal como complemento de las carpas para proteger a los invitados del viento, sol o lluvia según la temporada del evento.",
    "dimensiones": "10 m de largo x 2,5 m de alto",
    "material": "Lona reforzada",
    "capacidad": "Complemento de carpa",
    "color": "Blanco",
    "precio": 60000,
    "unidadPrecio": "por unidad / evento",
    "imagen": "images/carpa1.jpg",
    "imagenes": [
      "images/carpa1.jpg"
    ],
    "destacado": false
  },
  {
    "id": "car-003",
    "nombre": "Pista de baile modular",
    "categoria": "carpas-exteriores",
    "categoriaLabel": "Carpas y exteriores",
    "descripcion": "Piso modular para pista de baile en exteriores o jardines.",
    "descripcionLarga": "Piso modular de madera para pista de baile, ideal para instalar sobre pasto o superficies irregulares en matrimonios de exterior. Estructura firme y fácil de armar.",
    "dimensiones": "5 m x 5 m (ampliable)",
    "material": "Madera laminada / estructura modular",
    "capacidad": "Hasta 40 personas en pista",
    "color": "Madera clara",
    "precio": 180000,
    "unidadPrecio": "por evento (instalación incluida)",
    "imagen": "images/exterior1.jpg",
    "imagenes": [
      "images/exterior1.jpg"
    ],
    "destacado": false
  },
  {
    "id": "equ-001",
    "nombre": "Estufa cónica a gas",
    "categoria": "equipamiento",
    "categoriaLabel": "Equipamiento",
    "descripcion": "Estufa cónica para climatizar eventos en exteriores durante la noche.",
    "descripcionLarga": "Estufa cónica a gas de pie, ideal para climatizar terrazas y jardines durante celebraciones nocturnas, especialmente en temporadas frías.",
    "dimensiones": "2,2 m de alto",
    "material": "Acero",
    "capacidad": "Cobertura aprox. 15 m²",
    "color": "Acero cepillado",
    "precio": 25000,
    "unidadPrecio": "por unidad / evento",
    "imagen": "images/equipamiento1.jpg",
    "imagenes": [
      "images/equipamiento1.jpg"
    ],
    "destacado": true
  },
  {
    "id": "equ-002",
    "nombre": "Set de iluminación cálida",
    "categoria": "equipamiento",
    "categoriaLabel": "Equipamiento",
    "descripcion": "Guirnaldas de luz cálida para ambientación de carpas y exteriores.",
    "descripcionLarga": "Set de guirnaldas de luz cálida tipo festoon, ideales para ambientar carpas, jardines y terrazas, aportando una atmósfera cálida y romántica al evento.",
    "dimensiones": "20 m por set",
    "material": "Cable con luces LED",
    "capacidad": "Cobertura según metraje",
    "color": "Luz cálida",
    "precio": 45000,
    "unidadPrecio": "por set / evento",
    "imagen": "images/equipamiento1.jpg",
    "imagenes": [
      "images/equipamiento1.jpg"
    ],
    "destacado": false
  },
  {
    "id": "equ-003",
    "nombre": "Sistema de sonido básico",
    "categoria": "equipamiento",
    "categoriaLabel": "Equipamiento",
    "descripcion": "Equipo de sonido con parlantes y micrófono para ceremonias y discursos.",
    "descripcionLarga": "Sistema de sonido básico con parlantes activos y micrófono inalámbrico, ideal para ceremonias, discursos y ambientación musical de fondo en eventos empresariales y matrimonios.",
    "dimensiones": "2 parlantes + 1 micrófono",
    "material": "Equipo electrónico",
    "capacidad": "Cobertura hasta 150 personas",
    "color": "Negro",
    "precio": 90000,
    "unidadPrecio": "por evento",
    "imagen": "images/equipamiento1.jpg",
    "imagenes": [
      "images/equipamiento1.jpg"
    ],
    "destacado": false
  },
  {
    "id": "equ-004",
    "nombre": "Mesón de bar madera",
    "categoria": "equipamiento",
    "categoriaLabel": "Equipamiento",
    "descripcion": "Mesón de bar de madera para servicio de cócteles y bebestibles.",
    "descripcionLarga": "Mesón de bar en madera natural, ideal para el montaje de una estación de cócteles o bebestibles en matrimonios y eventos empresariales.",
    "dimensiones": "2 m x 0,6 m x 1,1 m alto",
    "material": "Madera",
    "capacidad": "Estación de servicio",
    "color": "Madera natural",
    "precio": 55000,
    "unidadPrecio": "por unidad / evento",
    "imagen": "images/equipamiento1.jpg",
    "imagenes": [
      "images/equipamiento1.jpg"
    ],
    "destacado": true
  },
  {
    "id": "dec-001",
    "nombre": "Centro de mesa floral",
    "categoria": "decoracion",
    "categoriaLabel": "Decoración",
    "descripcion": "Arreglo floral para centro de mesa, confeccionado con flores de estación.",
    "descripcionLarga": "Centro de mesa con flores de estación y follaje natural, confeccionado especialmente para tu evento. El colorido y las especies pueden ajustarse según la paleta de tu celebración.",
    "dimensiones": "Aprox. 40 cm de diámetro",
    "material": "Flores naturales y follaje",
    "capacidad": "Por mesa",
    "color": "A elección según temporada",
    "precio": 18000,
    "unidadPrecio": "por unidad / evento",
    "imagen": "images/deco1.jpg",
    "imagenes": [
      "images/deco1.jpg"
    ],
    "destacado": true
  },
  {
    "id": "dec-002",
    "nombre": "Candelabro decorativo",
    "categoria": "decoracion",
    "categoriaLabel": "Decoración",
    "descripcion": "Candelabro de metal para ambientar mesas y pasillos de ceremonia.",
    "descripcionLarga": "Candelabro decorativo de metal, ideal para ambientar mesas imperiales o el pasillo de la ceremonia con una luz cálida y romántica.",
    "dimensiones": "35 cm de alto",
    "material": "Metal",
    "capacidad": "Individual",
    "color": "Dorado apagado",
    "precio": 6000,
    "unidadPrecio": "por unidad / evento",
    "imagen": "images/deco1.jpg",
    "imagenes": [
      "images/deco1.jpg"
    ],
    "destacado": false
  },
  {
    "id": "dec-003",
    "nombre": "Base geométrica para centro de mesa",
    "categoria": "decoracion",
    "categoriaLabel": "Decoración",
    "descripcion": "Base decorativa de metal para elevar arreglos florales o vajilla.",
    "descripcionLarga": "Base decorativa de metal en diseño geométrico, pensada para elevar arreglos florales, postres o piezas de vajilla dentro del montaje de mesa.",
    "dimensiones": "25 cm de diámetro x 15 cm de alto",
    "material": "Metal",
    "capacidad": "Individual",
    "color": "Dorado apagado",
    "precio": 5000,
    "unidadPrecio": "por unidad / evento",
    "imagen": "images/deco1.jpg",
    "imagenes": [
      "images/deco1.jpg"
    ],
    "destacado": false
  }
];
