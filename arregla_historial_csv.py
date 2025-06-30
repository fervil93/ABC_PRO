input_file = "pnl_history.csv"
output_file = "pnl_history_arreglado.csv"

with open(input_file, "r") as fin, open(output_file, "w") as fout:
    for line in fin:
        columns = line.strip().split(",")
        if len(columns) == 9:
            # Añadir dos columnas vacías
            columns += ["", ""]
        fout.write(",".join(columns) + "\n")
print("Listo. Usa pnl_history_arreglado.csv como nuevo historial.")