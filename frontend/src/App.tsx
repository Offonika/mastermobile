import B24Assistant from './components/B24Assistant';
import styles from './App.module.css';

function App() {
  return (
    <div className={styles.container}>
      <header className={styles.header}>
        <h1 className={styles.title}>Ассистент MasterMobile</h1>
        <p className={styles.subtitle}>
          Чат-помощник внутри Bitrix24. Задайте вопрос или загрузите документ для анализа.
        </p>
      </header>
      <main className={styles.chatArea}>
        <B24Assistant />
      </main>
    </div>
  );
}

export default App;
