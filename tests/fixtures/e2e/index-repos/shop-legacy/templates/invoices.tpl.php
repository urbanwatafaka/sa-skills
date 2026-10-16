<table><?php while ($row = mysql_fetch_assoc($orders)): ?><tr><td><?= $row['order_id'] ?></td></tr><?php endwhile; ?></table>
