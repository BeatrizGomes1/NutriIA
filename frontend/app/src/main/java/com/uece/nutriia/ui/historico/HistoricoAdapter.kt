package com.uece.nutriia.ui.historico

import android.view.LayoutInflater
import android.view.ViewGroup
import androidx.core.content.ContextCompat
import androidx.recyclerview.widget.RecyclerView
import com.uece.nutriia.R
import com.uece.nutriia.data.model.Analise
import com.uece.nutriia.databinding.ItemAnaliseBinding

class HistoricoAdapter : RecyclerView.Adapter<HistoricoAdapter.AnaliseViewHolder>() {

    private val itens = mutableListOf<Analise>()

    fun atualizar(novosItens: List<Analise>) {
        itens.clear()
        itens.addAll(novosItens)
        notifyDataSetChanged()
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): AnaliseViewHolder {
        val binding = ItemAnaliseBinding.inflate(LayoutInflater.from(parent.context), parent, false)
        return AnaliseViewHolder(binding)
    }

    override fun onBindViewHolder(holder: AnaliseViewHolder, position: Int) {
        holder.bind(itens[position])
    }

    override fun getItemCount(): Int = itens.size

    class AnaliseViewHolder(
        private val binding: ItemAnaliseBinding
    ) : RecyclerView.ViewHolder(binding.root) {

        fun bind(analise: Analise) {
            val context = binding.root.context
            binding.txtNome.text = analise.nome
            binding.txtMarca.text = context.getString(
                R.string.marca_data_format,
                analise.marca,
                analise.dataRelativa
            )
            binding.itemThumb.setBackgroundResource(
                if (analise.thumbPeach) R.drawable.bg_thumb_peach else R.drawable.bg_thumb_mint
            )
            if (analise.recomendado) {
                binding.txtStatus.text = context.getString(R.string.recommended)
                binding.txtStatus.setTextColor(ContextCompat.getColor(context, R.color.green_primary))
            } else {
                binding.txtStatus.text = context.getString(R.string.not_recommended)
                binding.txtStatus.setTextColor(ContextCompat.getColor(context, R.color.danger))
            }
        }
    }
}
