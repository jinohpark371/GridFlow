import type { Post } from "@/lib/state";
import styles from "./FeedGrid.module.css";

interface Props {
  posts: Post[];
  onOpenPost: (postId: string) => void;
  onNewPost: () => void;
  onShowIntro: () => void;
}

export function FeedGrid({ posts, onOpenPost, onNewPost, onShowIntro }: Props) {
  return (
    <section className={styles.root}>
      <header className={styles.header}>
        <h1 className={styles.title}>GridFlow</h1>
        <button type="button" className={styles.help} onClick={onShowIntro} aria-label="사용법 보기">
          ?
        </button>
      </header>

      {posts.length === 0 ? (
        <div className={styles.empty}>
          <p>아직 게시물이 없어요</p>
          <p className={styles.emptyHint}>사진을 고르면 테마에 어울리는 순서를 추천해 드려요</p>
        </div>
      ) : (
        <ul className={styles.grid} aria-label="게시물 그리드">
          {posts.map((post) => (
            <li key={post.id}>
              <button
                type="button"
                className={styles.tile}
                onClick={() => onOpenPost(post.id)}
                aria-label={`게시물 열기 (사진 ${post.photos.length}장)`}
              >
                <img src={post.photos[0].url} alt="" />
                {post.photos.length > 1 && <span className={styles.carouselMark} data-carousel aria-hidden="true" />}
              </button>
            </li>
          ))}
        </ul>
      )}

      <button type="button" className={styles.fab} onClick={onNewPost}>
        + 새 게시물
      </button>
    </section>
  );
}
