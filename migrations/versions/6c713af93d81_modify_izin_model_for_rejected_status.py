"""Modify Izin model for rejected status

Revision ID: 6c713af93d81
Revises: 4c933411a49f
Create Date: 2025-08-26 01:25:43.830648

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = '6c713af93d81'
down_revision = '4c933411a49f'
branch_labels = None
depends_on = None



def upgrade():
    bind = op.get_bind()
    insp = inspect(bind)

    # ====== 1) tanggal_pengajuan ======
    cols = {c['name'] for c in insp.get_columns('izin')}
    if 'tanggal_pengajuan' not in cols:
        with op.batch_alter_table('izin', schema=None) as batch_op:
            batch_op.add_column(sa.Column('tanggal_pengajuan', sa.Date(), nullable=True))
    # isi nilai null -> tanggal hari ini
    op.execute("UPDATE izin SET tanggal_pengajuan = CURDATE() WHERE tanggal_pengajuan IS NULL")
    # pastikan NOT NULL
    with op.batch_alter_table('izin', schema=None) as batch_op:
        batch_op.alter_column('tanggal_pengajuan', existing_type=sa.Date(), nullable=False)

    # ====== 2) tanggal_berakhir nullable ======
    with op.batch_alter_table('izin', schema=None) as batch_op:
        batch_op.alter_column('tanggal_berakhir', existing_type=sa.DATE(), nullable=True)

    # ====== 3) urusan index/unique ======
    # Kita ingin UNIQUE (santri_id, edisi_id, status)
    # tapi sebelumnya ada UNIQUE lama: uq_izin_santri_edisi (santri_id, edisi_id)
    idx_list = insp.get_indexes('izin')
    idx_by_name = {i['name']: i for i in idx_list}

    # 3a) buat index non-unique penopang FK jika belum ada
    if 'idx_izin_santri_edisi' not in idx_by_name:
        with op.batch_alter_table('izin', schema=None) as batch_op:
            batch_op.create_index('idx_izin_santri_edisi', ['santri_id', 'edisi_id'], unique=False)

    # 3b) drop unique lama jika ada
    if 'uq_izin_santri_edisi' in idx_by_name:
        with op.batch_alter_table('izin', schema=None) as batch_op:
            batch_op.drop_index('uq_izin_santri_edisi')

    # 3c) buat unique baru jika belum ada
    if 'uq_izin_santri_edisi_status' not in idx_by_name:
        with op.batch_alter_table('izin', schema=None) as batch_op:
            batch_op.create_unique_constraint(
                'uq_izin_santri_edisi_status',
                ['santri_id', 'edisi_id', 'status']
            )


    # ### end Alembic commands ###


def downgrade():
    with op.batch_alter_table('izin', schema=None) as batch_op:
        # hapus unique baru jika ada
        batch_op.drop_constraint('uq_izin_santri_edisi_status', type_='unique')
        # buat kembali unique lama
        batch_op.create_index('uq_izin_santri_edisi', ['santri_id', 'edisi_id'], unique=True)
        # hapus index non-unique penopang
        batch_op.drop_index('idx_izin_santri_edisi')
        # balikan tanggal_berakhir ke NOT NULL
        batch_op.alter_column('tanggal_berakhir', existing_type=sa.DATE(), nullable=False)
        # drop tanggal_pengajuan
        batch_op.drop_column('tanggal_pengajuan')


    # ### end Alembic commands ###
