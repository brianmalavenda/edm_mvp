# Test
Cada documento en la carpeta /docs tiene que generar como salida por lo menos una nota de este estilo en el modo de ejecución "preview". Para eso se ejecuta el proyecto con esta linea python run_local.py preview test/docs/prueba_0X.docx

ESQUEMA NOTA:
--- Nota XX ---
  Volanta : [texto volanta] | no puede ser vacio
  Título  : [texto titulo] | no puede ser vacio
  Copete  : [texto copete] | no puede ser vacio
  Categoría: [texto categoria] | puede ser vacio, en ese caso quedará con el valor "(sin categoría)"
  Tags    : [texto etiqueta] | puede ser vacio, en ese caso quedará con el valor "(sin tags)"
  Imagen  : si/no depende si tiene o no imagen
  Párrafos de cuerpo: [cantidad numerica de paraffos en el cuerpo de la nota] | no puede ser vacio

# prueba_01.docx
La salida seran dos elementos de NOTA donde ambas notas tendran etiqueta y categorías. Solo la primera tiene imagen.

# prueba_02.docx
La salida seran 10 elementos de NOTA. 4 NOTAS tendrán imagen. Todas cumplen con que la volanta, el titulo, el copete y el cuerpo no estan vacios. Ninguna tiene categoria ni etiquetas pero igual es valido.

# prueba_03.docx
El documento tiene al principio un índice antes de la primera NOTA con volanta. Probamos que se haya generado igual las 13 notas a la salida a pesar de tener un agregado al principio del documento. Ninguna nota tiene etiquetas ni categorías. Se esperan 4 notas con imagen cargada.