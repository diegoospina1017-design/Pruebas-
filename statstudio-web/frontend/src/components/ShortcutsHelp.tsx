import styles from "./Modal.module.css";

export function ShortcutsHelp({ onClose }: { onClose: () => void }) {
  return (
    <div className={styles.backdrop} onClick={onClose}>
      <div className={styles.modal} onClick={(e) => e.stopPropagation()} style={{ maxWidth: 480 }}>
        <header><h3>Atajos de teclado</h3><button onClick={onClose}>×</button></header>
        <table>
          <tbody>
            <tr><td><kbd>Ctrl/Cmd+O</kbd></td><td>Importar archivo</td></tr>
            <tr><td><kbd>Ctrl/Cmd+S</kbd></td><td>Guardar proyecto</td></tr>
            <tr><td><kbd>Ctrl/Cmd+P</kbd></td><td>Reporte HTML</td></tr>
            <tr><td><kbd>Supr</kbd> / <kbd>Backspace</kbd></td><td>Limpiar celdas seleccionadas</td></tr>
            <tr><td><kbd>Ctrl/Cmd+Z</kbd></td><td>Deshacer (grid)</td></tr>
            <tr><td><kbd>Ctrl/Cmd+Y</kbd></td><td>Rehacer (grid)</td></tr>
            <tr><td><kbd>?</kbd></td><td>Esta ayuda</td></tr>
            <tr><td><kbd>Esc</kbd></td><td>Cerrar diálogos</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}
